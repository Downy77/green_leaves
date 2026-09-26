from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Any, AsyncIterator, Protocol, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from backend.core.config import provider_connection


class AgentStore(Protocol):
    def setting(self, key: str, default: str = "") -> str:
        ...

    def recent_context(self, conversation_id: str, limit: int = 8) -> list[dict[str, str]]:
        ...

    def search_knowledge(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        ...

    def active_memories(self, query: str, limit: int = 6) -> list[dict[str, Any]]:
        ...


class AgentState(TypedDict, total=False):
    conversation_id: str
    user_message: str
    web_mode: str
    model: str
    provider: str
    attachments: list[dict[str, Any]]
    memory_enabled: bool
    knowledge_enabled: bool
    context_enabled: bool
    history: list[dict[str, str]]
    memories: list[dict[str, Any]]
    knowledge: list[dict[str, Any]]
    web_results: list[dict[str, Any]]
    route: str
    context_text: str


@dataclass(slots=True)
class AgentTrace:
    route: str
    knowledge_count: int
    memory_count: int
    web_result_count: int


class CouplingAgentRuntime:
    """LangGraph orchestration for the clone's assistant workflow.

    The graph prepares all durable context before generation. The generation
    step is streamed separately so the existing Server-Sent Events contract
    stays compatible with the current frontend.
    """

    def __init__(self, store: AgentStore):
        self.store = store
        self.graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(AgentState)
        graph.add_node("prepare_context", self._prepare_context)
        graph.add_node("route_request", self._route_request)
        graph.add_edge(START, "prepare_context")
        graph.add_edge("prepare_context", "route_request")
        graph.add_edge("route_request", END)
        return graph.compile(checkpointer=MemorySaver())

    async def _prepare_context(self, state: AgentState) -> dict[str, Any]:
        query = state.get("user_message", "").strip()
        conversation_id = state["conversation_id"]
        context_enabled = self.store.setting("context_enabled", "true") == "true"
        memory_enabled = self.store.setting("memory_enabled", "true") == "true"
        knowledge_enabled = self.store.setting("knowledge_enabled", "true") == "true"
        history = self.store.recent_context(conversation_id, limit=12 if context_enabled else 6)
        memories: list[dict[str, Any]] = []
        knowledge: list[dict[str, Any]] = []

        if memory_enabled:
            memories = self.store.active_memories(query, limit=6)
        if knowledge_enabled:
            knowledge = self.store.search_knowledge(query, limit=5)

        return {
            "memory_enabled": memory_enabled,
            "knowledge_enabled": knowledge_enabled,
            "context_enabled": context_enabled,
            "history": history,
            "memories": memories,
            "knowledge": knowledge,
            "web_results": [],
        }

    async def _route_request(self, state: AgentState) -> dict[str, Any]:
        mode = state.get("web_mode", "auto")
        query = state.get("user_message", "").strip()
        should_search = mode == "manual" or (mode == "auto" and self._looks_time_sensitive(query))
        web_results: list[dict[str, Any]] = []
        if should_search and os.getenv("TAVILY_API_KEY"):
            web_results = await self._search_web(query)

        context_text = self._format_context(state, web_results)
        return {
            "route": "web_research" if should_search else "knowledge_assistant",
            "web_results": web_results,
            "context_text": context_text,
        }

    async def _search_web(self, query: str) -> list[dict[str, Any]]:
        try:
            from langchain_tavily import TavilySearch

            tool = TavilySearch(max_results=5)
            result = await tool.ainvoke({"query": query})
            if isinstance(result, dict):
                raw = result.get("results", result.get("answer", []))
            else:
                raw = result
            if isinstance(raw, str):
                return [{"content": raw}]
            return list(raw or [])[:5]
        except Exception:
            return []

    @staticmethod
    def _looks_time_sensitive(query: str) -> bool:
        keywords = (
            "今天",
            "现在",
            "最新",
            "最近",
            "新闻",
            "价格",
            "天气",
            "政策",
            "官网",
            "发布",
            "current",
            "latest",
            "today",
        )
        lowered = query.lower()
        return any(keyword in lowered for keyword in keywords) or "http://" in lowered or "https://" in lowered

    @staticmethod
    def _format_context(state: AgentState, web_results: list[dict[str, Any]]) -> str:
        blocks: list[str] = []
        memories = state.get("memories", [])
        knowledge = state.get("knowledge", [])

        if memories:
            blocks.append(
                "长期记忆:\n"
                + "\n".join(f"- {item.get('content', '')}" for item in memories)
            )
        if knowledge:
            blocks.append(
                "知识库检索:\n"
                + "\n".join(
                    f"- {item.get('title', '未命名')}: {item.get('content', '')[:700]}"
                    for item in knowledge
                )
            )
        if web_results:
            lines = []
            for item in web_results:
                title = item.get("title") or item.get("name") or "网页结果"
                content = item.get("content") or item.get("snippet") or item.get("url") or ""
                lines.append(f"- {title}: {content[:700]}")
            blocks.append("联网检索:\n" + "\n".join(lines))
        return "\n\n".join(blocks) or "没有额外上下文。"

    async def prepare(self, *, conversation_id: str, user_message: str, web_mode: str, model: str, provider: str, attachments: list[dict[str, Any]]) -> AgentState:
        state: AgentState = {
            "conversation_id": conversation_id,
            "user_message": user_message,
            "web_mode": web_mode,
            "model": model,
            "provider": provider,
            "attachments": attachments,
        }
        config = {"configurable": {"thread_id": conversation_id}}
        return await self.graph.ainvoke(state, config=config)

    async def stream_answer(
        self,
        *,
        conversation_id: str,
        user_message: str,
        web_mode: str,
        model: str,
        provider: str,
        attachments: list[dict[str, Any]],
    ) -> AsyncIterator[str]:
        state = await self.prepare(
            conversation_id=conversation_id,
            user_message=user_message,
            web_mode=web_mode,
            model=model,
            provider=provider,
            attachments=attachments,
        )

        async for piece in self.stream_prepared_answer(state):
            yield piece

    async def stream_prepared_answer(self, state: AgentState) -> AsyncIterator[str]:
        api_key, _ = provider_connection(state["provider"])
        if api_key:
            async for piece in self._stream_model(state):
                yield piece
            return

        async for piece in self._stream_local(state):
            yield piece

    async def _stream_model(self, state: AgentState) -> AsyncIterator[str]:
        from langchain_openai import ChatOpenAI

        api_key, base_url = provider_connection(state["provider"])

        model = ChatOpenAI(
            model=state["model"],
            api_key=api_key,
            base_url=base_url,
            temperature=0.2,
            streaming=True,
        )
        messages = self._model_messages(state)
        try:
            async for chunk in model.astream(messages):
                text = self._message_text(chunk)
                if text:
                    yield text
        except Exception as exc:
            yield f"\n\n> 真实模型调用失败，已回退到本地提示：{exc}\n"

    async def _stream_local(self, state: AgentState) -> AsyncIterator[str]:
        message = state.get("user_message", "").strip() or "空消息"
        attachment_count = len(state.get("attachments", []))
        route = state.get("route", "knowledge_assistant")
        knowledge_count = len(state.get("knowledge", []))
        memory_count = len(state.get("memories", []))
        web_count = len(state.get("web_results", []))
        answer = (
            f"我已收到你的问题：**{message}**。\n\n"
            "当前使用 LangGraph 本地工作流完成了上下文准备。"
            f"本次路由为 `{route}`，命中知识库 {knowledge_count} 条、长期记忆 {memory_count} 条、联网结果 {web_count} 条。"
        )
        if attachment_count:
            answer += f"\n\n我看到了 {attachment_count} 个附件，已保存到本地工作区。"
        answer += (
            "\n\n配置所选服务商的 API Key 后会自动切换到 LangChain 流式模型；"
            "配置 `TAVILY_API_KEY` 后可以启用联网检索。"
        )
        for chunk in self._chunk_text(answer):
            yield chunk
            await asyncio.sleep(0.012)

    def _model_messages(self, state: AgentState) -> list[BaseMessage]:
        system = (
            "你是耦合生命工作台中的中文 AI 助手。"
            "回答要清晰、务实、可执行；如果使用了知识库、记忆或联网结果，"
            "请优先基于这些上下文，并明确区分已知事实与推断。"
            f"\n\n当前任务路由：{state.get('route', 'knowledge_assistant')}"
            f"\n\n上下文：\n{state.get('context_text', '没有额外上下文。')}"
        )
        messages: list[BaseMessage] = [SystemMessage(content=system)]
        for item in state.get("history", []):
            if item.get("role") == "assistant":
                messages.append(AIMessage(content=item.get("content", "")))
            else:
                messages.append(HumanMessage(content=item.get("content", "")))
        if not messages or not isinstance(messages[-1], HumanMessage):
            messages.append(HumanMessage(content=state.get("user_message", "")))
        return messages

    @staticmethod
    def _message_text(message: Any) -> str:
        content = getattr(message, "content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in content
            )
        return str(content or "")

    @staticmethod
    def _chunk_text(text: str, size: int = 18) -> list[str]:
        return [text[index:index + size] for index in range(0, len(text), size)]
