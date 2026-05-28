"""JARVIS agent architecture (Phase 70) — facades over existing runtimes."""

from agents.base import AgentCapability, AgentDelegation, AgentId
from agents.conversation_agent import ConversationAgent, get_conversation_agent
from agents.coding_agent import CodingAgent, get_coding_agent
from agents.executive_agent import ExecutiveAgent, get_executive_agent
from agents.intent_routing import agent_for_intent
from agents.memory_agent import MemoryAgent, get_memory_agent
from agents.operator_agent import OperatorAgent, get_operator_agent
from agents.planning_agent import PlanningAgent, get_planning_agent
from agents.research_agent import ResearchAgent, get_research_agent

__all__ = [
    "AgentCapability",
    "AgentDelegation",
    "AgentId",
    "ConversationAgent",
    "CodingAgent",
    "ExecutiveAgent",
    "MemoryAgent",
    "OperatorAgent",
    "PlanningAgent",
    "ResearchAgent",
    "agent_for_intent",
    "get_conversation_agent",
    "get_coding_agent",
    "get_executive_agent",
    "get_memory_agent",
    "get_operator_agent",
    "get_planning_agent",
    "get_research_agent",
]
