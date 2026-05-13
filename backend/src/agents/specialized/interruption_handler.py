"""
人工干预处理器
处理需要人工审查和批准的敏感操作
"""
import logging
import asyncio
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field

from agents.base_agent import BaseAgent, AgentCapabilities, AgentStatus

logger = logging.getLogger(__name__)


class InterventionType(Enum):
    """干预类型"""
    SENSITIVE_OPERATION = "sensitive_operation"  # 敏感操作（删除、修改等）
    LOW_CONFIDENCE = "low_confidence"  # 低置信度决策
    TOOL_FAILURE = "tool_failure"  # 连续工具调用失败
    SAFETY_CHECK = "safety_check"  # 安全检查
    USER_REQUEST = "user_request"  # 用户主动请求干预


class InterventionStatus(Enum):
    """干预状态"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class InterventionRequest:
    """干预请求"""
    request_id: str
    type: InterventionType
    description: str
    context: Dict[str, Any] = field(default_factory=dict)
    status: InterventionStatus = InterventionStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    resolved_at: Optional[str] = None
    resolver: Optional[str] = None
    resolution_notes: Optional[str] = None
    timeout_seconds: int = 300


class InterruptionHandler(BaseAgent):
    """
    人工干预处理器

    功能:
    - 拦截敏感操作并请求人工审批
    - 管理干预请求的生命周期
    - 记录所有干预操作的审计日志
    - 支持审批超时和自动拒绝
    """

    # 敏感操作关键词
    SENSITIVE_KEYWORDS = [
        "delete", "remove", "drop", "truncate",
        "update", "modify", "alter", "change",
        "grant", "revoke", "permission",
        "deploy", "publish", "release",
        "shutdown", "restart", "stop",
        "exec", "execute", "eval",
    ]

    def __init__(
        self,
        agent_id: str = "interruption_handler",
        name: str = "Interruption Handler",
        description: str = "人工干预处理器，管理需要人工审查的操作",
    ):
        super().__init__(agent_id=agent_id, name=name, description=description)
        self.capabilities = AgentCapabilities(
            can_chat=False,
            can_tool_call=False,
            can_plan_execute=False,
            can_react=False,
            supported_intents=[],
        )
        self._pending_requests: Dict[str, InterventionRequest] = {}
        self._audit_log: List[Dict[str, Any]] = []
        self._approval_callbacks: Dict[str, Callable] = {}

    async def initialize(self):
        """初始化干预处理器"""
        if self._initialized:
            return
        self._initialized = True
        self.status = AgentStatus(status="idle")
        logger.info(f"人工干预处理器初始化完成: {self.agent_id}")

    async def process_message(
        self,
        session_id: str,
        message_id: str,
        message_content: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        处理干预请求

        Args:
            session_id: 会话ID
            message_id: 消息ID
            message_content: 消息内容
            context: 上下文信息

        Returns:
            处理结果
        """
        try:
            context = context or {}
            action = context.get("action", "check")

            if action == "check":
                return await self._check_intervention_needed(session_id, context)
            elif action == "approve":
                return await self._approve_request(session_id, message_content, context)
            elif action == "reject":
                return await self._reject_request(session_id, message_content, context)
            elif action == "list":
                return self._list_pending_requests(session_id)
            else:
                return {"response": "未知的干预操作", "message_id": f"resp_{message_id}"}

        except Exception as e:
            logger.error(f"干预处理器执行失败: {e}")
            return {
                "response": f"干预处理失败: {str(e)}",
                "message_id": f"error_{message_id}",
                "is_error": True,
            }

    async def _check_intervention_needed(
        self, session_id: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        检查是否需要人工干预

        Args:
            session_id: 会话ID
            context: 上下文信息

        Returns:
            检查结果
        """
        interventions = []

        # 检查1: 敏感工具调用
        tool_calls = context.get("tool_calls", [])
        for tool_call in tool_calls:
            tool_name = tool_call.get("tool_name", "").lower()
            if any(kw in tool_name for kw in self.SENSITIVE_KEYWORDS):
                interventions.append({
                    "type": InterventionType.SENSITIVE_OPERATION,
                    "reason": f"敏感工具调用: {tool_name}",
                    "tool_name": tool_name,
                    "tool_input": tool_call.get("tool_input", {}),
                })

        # 检查2: 多次工具调用失败
        tool_results = context.get("tool_results", [])
        failed_calls = [r for r in tool_results if r.get("is_error")]
        if len(failed_calls) >= 3:
            interventions.append({
                "type": InterventionType.TOOL_FAILURE,
                "reason": f"连续工具调用失败: {len(failed_calls)}次",
                "failed_tools": [r.get("tool_name") for r in failed_calls],
            })

        # 检查3: 低置信度
        confidence = context.get("intent_confidence", 1.0)
        if confidence < 0.3:
            interventions.append({
                "type": InterventionType.LOW_CONFIDENCE,
                "reason": f"意图置信度过低: {confidence:.2f}",
                "confidence": confidence,
            })

        # 创建干预请求
        created_requests = []
        for intervention in interventions:
            request = self.create_intervention_request(
                intervention_type=intervention["type"],
                description=intervention["reason"],
                context={
                    "session_id": session_id,
                    **intervention,
                },
            )
            created_requests.append(request)

        requires_intervention = len(created_requests) > 0

        logger.info(f"干预检查完成: requires={requires_intervention}, count={len(created_requests)}")

        return {
            "requires_intervention": requires_intervention,
            "interventions": created_requests,
            "count": len(created_requests),
        }

    def create_intervention_request(
        self,
        intervention_type: InterventionType,
        description: str,
        context: Optional[Dict[str, Any]] = None,
        timeout_seconds: int = 300,
    ) -> InterventionRequest:
        """
        创建干预请求

        Args:
            intervention_type: 干预类型
            description: 描述
            context: 上下文
            timeout_seconds: 超时时间

        Returns:
            干预请求
        """
        import uuid
        request_id = f"intervention_{uuid.uuid4().hex[:12]}"

        request = InterventionRequest(
            request_id=request_id,
            type=intervention_type,
            description=description,
            context=context or {},
            timeout_seconds=timeout_seconds,
        )

        self._pending_requests[request_id] = request

        # 记录审计日志
        self._log_audit("created", request_id, {
            "type": intervention_type.value,
            "description": description,
        })

        # 设置超时
        asyncio.create_task(self._handle_timeout(request_id, timeout_seconds))

        logger.info(f"创建干预请求: {request_id} ({intervention_type.value})")
        return request

    async def _approve_request(
        self, session_id: str, approver: str = "user", context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """批准干预请求"""
        context = context or {}
        request_id = context.get("request_id")

        if not request_id or request_id not in self._pending_requests:
            return {"response": f"干预请求不存在: {request_id}", "approved": False}

        request = self._pending_requests[request_id]
        request.status = InterventionStatus.APPROVED
        request.resolved_at = datetime.now().isoformat()
        request.resolver = approver
        request.resolution_notes = context.get("notes", "已批准")

        self._log_audit("approved", request_id, {"approver": approver})

        # 执行回调
        if request_id in self._approval_callbacks:
            try:
                await self._approval_callbacks[request_id](request, approved=True)
            except Exception as e:
                logger.error(f"审批回调执行失败: {e}")

        del self._pending_requests[request_id]

        return {
            "response": f"干预请求 {request_id} 已批准",
            "request_id": request_id,
            "approved": True,
        }

    async def _reject_request(
        self, session_id: str, rejector: str = "user", context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """拒绝干预请求"""
        context = context or {}
        request_id = context.get("request_id")

        if not request_id or request_id not in self._pending_requests:
            return {"response": f"干预请求不存在: {request_id}", "rejected": False}

        request = self._pending_requests[request_id]
        request.status = InterventionStatus.REJECTED
        request.resolved_at = datetime.now().isoformat()
        request.resolver = rejector
        request.resolution_notes = context.get("notes", "已拒绝")

        self._log_audit("rejected", request_id, {"rejector": rejector})

        if request_id in self._approval_callbacks:
            try:
                await self._approval_callbacks[request_id](request, approved=False)
            except Exception as e:
                logger.error(f"审批回调执行失败: {e}")

        del self._pending_requests[request_id]

        return {
            "response": f"干预请求 {request_id} 已拒绝",
            "request_id": request_id,
            "rejected": True,
        }

    def _list_pending_requests(self, session_id: str) -> Dict[str, Any]:
        """列出待处理的干预请求"""
        pending = [
            {
                "request_id": r.request_id,
                "type": r.type.value,
                "description": r.description,
                "status": r.status.value,
                "created_at": r.created_at,
                "timeout_seconds": r.timeout_seconds,
            }
            for r in self._pending_requests.values()
            if r.status == InterventionStatus.PENDING
        ]

        return {
            "response": f"待处理干预请求: {len(pending)} 个",
            "pending_requests": pending,
            "count": len(pending),
        }

    async def _handle_timeout(self, request_id: str, timeout_seconds: int):
        """处理干预请求超时"""
        await asyncio.sleep(timeout_seconds)

        if request_id in self._pending_requests:
            request = self._pending_requests[request_id]
            if request.status == InterventionStatus.PENDING:
                request.status = InterventionStatus.TIMEOUT
                request.resolved_at = datetime.now().isoformat()
                request.resolution_notes = "超时自动取消"

                self._log_audit("timeout", request_id, {"timeout_seconds": timeout_seconds})

                if request_id in self._approval_callbacks:
                    try:
                        await self._approval_callbacks[request_id](request, approved=False)
                    except Exception as e:
                        logger.error(f"超时回调执行失败: {e}")

                del self._pending_requests[request_id]
                logger.info(f"干预请求超时: {request_id}")

    def register_callback(self, request_id: str, callback: Callable):
        """注册审批结果回调"""
        self._approval_callbacks[request_id] = callback

    def get_pending_count(self) -> int:
        """获取待处理干预请求数量"""
        return len([
            r for r in self._pending_requests.values()
            if r.status == InterventionStatus.PENDING
        ])

    def _log_audit(self, action: str, request_id: str, details: Dict[str, Any]):
        """记录审计日志"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "request_id": request_id,
            "details": details,
        }
        self._audit_log.append(entry)

        if len(self._audit_log) > 10000:
            self._audit_log = self._audit_log[-5000:]

        logger.info(f"干预审计: {action} - {request_id}")

    def get_audit_log(
        self, limit: int = 100, request_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """获取审计日志"""
        if request_id:
            return [e for e in self._audit_log if e["request_id"] == request_id]
        return self._audit_log[-limit:]

    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        return {
            "agent_id": self.agent_id,
            "status": "healthy" if self._initialized else "not_initialized",
            "pending_requests": self.get_pending_count(),
            "audit_log_entries": len(self._audit_log),
        }

    async def cleanup(self):
        """清理资源"""
        self._pending_requests.clear()
        self._approval_callbacks.clear()
