"""API v1 路由聚合。"""

from fastapi import APIRouter

from app.api.v1.audit_logs import router as audit_logs_router
from app.api.v1.auth import router as auth_router
from app.api.v1.business_requests import router as business_requests_router
from app.api.v1.customer_contacts import router as customer_contacts_router
from app.api.v1.customer_titles import router as customer_titles_router
from app.api.v1.enterprises import router as enterprises_router
from app.api.v1.exceptions import router as exceptions_router
from app.api.v1.invoice_batches import router as invoice_batches_router
from app.api.v1.invoice_requests import router as invoice_requests_router
from app.api.v1.invoice_tasks import router as invoice_tasks_router
from app.api.v1.organizations import router as organizations_router
from app.api.v1.product_rules import router as product_rules_router
from app.api.v1.batch_operations import router as batch_operations_router
from app.api.v1.channels import router as channels_router
from app.api.v1.recognitions import router as recognitions_router
from app.api.v1.sse import router as sse_router
from app.api.v1.statistics import router as statistics_router
from app.api.v1.submission_links import router as submission_links_router
from app.api.v1.submissions import router as submissions_router
from app.api.v1.users import router as users_router
from app.api.v1.work_items import router as work_items_router
from app.api.v1.wechat import router as wechat_router
from app.api.v1.system_config import router as system_config_router
from app.api.v1.health import router as health_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth_router, tags=["认证"])
api_router.include_router(users_router, tags=["用户管理"])
api_router.include_router(enterprises_router, tags=["企业管理"])
api_router.include_router(customer_titles_router, tags=["客户抬头"])
api_router.include_router(customer_contacts_router, tags=["客户联系人"])
api_router.include_router(product_rules_router, tags=["商品规则"])
api_router.include_router(business_requests_router, tags=["业务申请"])
api_router.include_router(invoice_requests_router, tags=["开票请求"])
api_router.include_router(invoice_batches_router, tags=["开票批次"])
api_router.include_router(invoice_tasks_router, tags=["开票任务"])
api_router.include_router(work_items_router, tags=["工作项"])
api_router.include_router(exceptions_router, tags=["异常处理"])
api_router.include_router(statistics_router, tags=["数据统计"])
api_router.include_router(audit_logs_router, tags=["审计日志"])
api_router.include_router(organizations_router, tags=["组织架构"])
api_router.include_router(recognitions_router, tags=["AI识别"])
api_router.include_router(channels_router, tags=["通道管理"])
api_router.include_router(sse_router, tags=["实时推送"])
api_router.include_router(batch_operations_router, tags=["批量操作"])
api_router.include_router(submissions_router, tags=["客户提交"])
api_router.include_router(submission_links_router, tags=["提交链接管理"])
api_router.include_router(wechat_router, tags=["微信集成"])
api_router.include_router(system_config_router, tags=["系统配置"])
api_router.include_router(health_router, tags=["健康检查"])
