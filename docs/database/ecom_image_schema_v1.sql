-- 电商作图项目：数据库初始化脚本（PostgreSQL）
-- 适用版本：PostgreSQL 14+
-- 说明：
-- 1. 本脚本包含表结构、索引、约束、中文注释、updated_at 自动更新时间触发器。
-- 2. UUID 默认使用 pgcrypto 扩展提供的 gen_random_uuid()。
-- 3. 若你的数据库未安装 pgcrypto，请先确认有安装权限。

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- =========================================================
-- 通用函数：自动更新时间
-- =========================================================
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS trigger AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION set_updated_at() IS '通用触发器函数：在更新数据时自动刷新 updated_at 字段';

-- =========================================================
-- 1. users 用户表
-- =========================================================
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    nickname VARCHAR(100),
    avatar_url VARCHAR(500),
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    email_verified BOOLEAN NOT NULL DEFAULT FALSE,
    last_login_at TIMESTAMPTZ,
    last_login_ip INET,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT uq_users_email UNIQUE (email),
    CONSTRAINT ck_users_status CHECK (status IN ('active', 'disabled', 'pending_verification'))
);

COMMENT ON TABLE users IS '用户主表，保存系统注册用户的基础身份信息与登录状态';
COMMENT ON COLUMN users.id IS '用户主键ID，UUID';
COMMENT ON COLUMN users.email IS '用户登录邮箱，唯一';
COMMENT ON COLUMN users.password_hash IS '用户密码哈希值，不保存明文密码';
COMMENT ON COLUMN users.nickname IS '用户昵称';
COMMENT ON COLUMN users.avatar_url IS '用户头像地址';
COMMENT ON COLUMN users.status IS '用户状态：active=正常，disabled=禁用，pending_verification=待验证';
COMMENT ON COLUMN users.email_verified IS '邮箱是否已验证';
COMMENT ON COLUMN users.last_login_at IS '最近一次登录时间';
COMMENT ON COLUMN users.last_login_ip IS '最近一次登录IP';
COMMENT ON COLUMN users.created_at IS '创建时间';
COMMENT ON COLUMN users.updated_at IS '更新时间';
COMMENT ON COLUMN users.deleted_at IS '软删除时间，为空表示未删除';

CREATE INDEX IF NOT EXISTS idx_users_status ON users(status);
CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at DESC);

CREATE TRIGGER trg_users_set_updated_at
BEFORE UPDATE ON users
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- =========================================================
-- 2. refresh_tokens 刷新令牌表
-- =========================================================
CREATE TABLE IF NOT EXISTS refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    token_hash VARCHAR(255) NOT NULL,
    device_id VARCHAR(128),
    user_agent VARCHAR(500),
    ip_address INET,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    replaced_by_token_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_refresh_tokens_token_hash UNIQUE (token_hash),
    CONSTRAINT fk_refresh_tokens_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_refresh_tokens_replaced_by_token_id FOREIGN KEY (replaced_by_token_id) REFERENCES refresh_tokens(id) ON DELETE SET NULL
);

COMMENT ON TABLE refresh_tokens IS '刷新令牌表，用于维护登录会话、令牌轮换、撤销登录与设备会话';
COMMENT ON COLUMN refresh_tokens.id IS '刷新令牌记录主键ID';
COMMENT ON COLUMN refresh_tokens.user_id IS '所属用户ID';
COMMENT ON COLUMN refresh_tokens.token_hash IS '刷新令牌哈希值，不保存明文令牌';
COMMENT ON COLUMN refresh_tokens.device_id IS '设备标识，可用于区分不同终端';
COMMENT ON COLUMN refresh_tokens.user_agent IS '登录设备的浏览器或客户端标识';
COMMENT ON COLUMN refresh_tokens.ip_address IS '签发该刷新令牌时的客户端IP';
COMMENT ON COLUMN refresh_tokens.expires_at IS '刷新令牌过期时间';
COMMENT ON COLUMN refresh_tokens.revoked_at IS '刷新令牌撤销时间，为空表示未撤销';
COMMENT ON COLUMN refresh_tokens.replaced_by_token_id IS '令牌轮换后替代当前令牌的新令牌ID';
COMMENT ON COLUMN refresh_tokens.created_at IS '创建时间';
COMMENT ON COLUMN refresh_tokens.updated_at IS '更新时间';

CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_expires_at ON refresh_tokens(expires_at);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_active ON refresh_tokens(user_id, revoked_at, expires_at);

CREATE TRIGGER trg_refresh_tokens_set_updated_at
BEFORE UPDATE ON refresh_tokens
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- =========================================================
-- 3. audit_logs 审计日志表
-- =========================================================
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID,
    action VARCHAR(100) NOT NULL,
    object_type VARCHAR(50),
    object_id UUID,
    request_id VARCHAR(64),
    ip_address INET,
    user_agent VARCHAR(500),
    payload JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_audit_logs_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

COMMENT ON TABLE audit_logs IS '审计日志表，记录登录、任务创建、文件下载、编辑等关键行为';
COMMENT ON COLUMN audit_logs.id IS '审计日志主键ID';
COMMENT ON COLUMN audit_logs.user_id IS '操作用户ID，匿名操作可为空';
COMMENT ON COLUMN audit_logs.action IS '审计动作，例如 auth.login、task.create、result.download';
COMMENT ON COLUMN audit_logs.object_type IS '被操作对象类型，例如 task、result、auth';
COMMENT ON COLUMN audit_logs.object_id IS '被操作对象ID';
COMMENT ON COLUMN audit_logs.request_id IS '请求链路ID，用于追踪一次请求的日志';
COMMENT ON COLUMN audit_logs.ip_address IS '操作来源IP';
COMMENT ON COLUMN audit_logs.user_agent IS '操作来源客户端标识';
COMMENT ON COLUMN audit_logs.payload IS '附加审计数据，JSONB格式';
COMMENT ON COLUMN audit_logs.created_at IS '创建时间';

CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_audit_logs_object ON audit_logs(object_type, object_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_payload_gin ON audit_logs USING GIN (payload);

-- =========================================================
-- 4. idempotency_keys 幂等键表
-- =========================================================
CREATE TABLE IF NOT EXISTS idempotency_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    request_key VARCHAR(128) NOT NULL,
    request_hash VARCHAR(128) NOT NULL,
    endpoint VARCHAR(255) NOT NULL,
    response_status INTEGER,
    response_body JSONB,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_idempotency_user_key UNIQUE (user_id, request_key),
    CONSTRAINT fk_idempotency_keys_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

COMMENT ON TABLE idempotency_keys IS '幂等键表，用于防止重复点击或重放请求导致重复创建任务';
COMMENT ON COLUMN idempotency_keys.id IS '幂等记录主键ID';
COMMENT ON COLUMN idempotency_keys.user_id IS '所属用户ID';
COMMENT ON COLUMN idempotency_keys.request_key IS '客户端提交的幂等键';
COMMENT ON COLUMN idempotency_keys.request_hash IS '请求体摘要哈希，用于校验是否为相同请求';
COMMENT ON COLUMN idempotency_keys.endpoint IS '请求接口路径';
COMMENT ON COLUMN idempotency_keys.response_status IS '首次请求响应状态码';
COMMENT ON COLUMN idempotency_keys.response_body IS '首次请求响应体摘要，JSONB格式';
COMMENT ON COLUMN idempotency_keys.expires_at IS '幂等记录过期时间';
COMMENT ON COLUMN idempotency_keys.created_at IS '创建时间';

CREATE INDEX IF NOT EXISTS idx_idempotency_expires_at ON idempotency_keys(expires_at);

-- =========================================================
-- 5. tasks 任务主表
-- =========================================================
CREATE TABLE IF NOT EXISTS tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    task_type VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    title VARCHAR(255),
    platform VARCHAR(50),
    biz_id VARCHAR(100),
    source_task_id UUID,
    parent_task_id UUID,
    current_step VARCHAR(100),
    progress_percent NUMERIC(5,2) NOT NULL DEFAULT 0,
    input_summary JSONB,
    params JSONB,
    runtime_snapshot JSONB,
    result_summary JSONB,
    error_code VARCHAR(100),
    error_message TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT fk_tasks_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_tasks_source_task_id FOREIGN KEY (source_task_id) REFERENCES tasks(id) ON DELETE SET NULL,
    CONSTRAINT fk_tasks_parent_task_id FOREIGN KEY (parent_task_id) REFERENCES tasks(id) ON DELETE SET NULL,
    CONSTRAINT ck_tasks_task_type CHECK (task_type IN ('main_image', 'detail_page', 'image_edit')),
    CONSTRAINT ck_tasks_status CHECK (status IN ('pending', 'queued', 'running', 'succeeded', 'failed', 'partial_failed', 'cancelled')),
    CONSTRAINT ck_tasks_progress_percent CHECK (progress_percent >= 0 AND progress_percent <= 100),
    CONSTRAINT ck_tasks_retry_count CHECK (retry_count >= 0)
);

COMMENT ON TABLE tasks IS '任务主表，统一记录主图生成、详情图生成、局部编辑等任务';
COMMENT ON COLUMN tasks.id IS '任务主键ID';
COMMENT ON COLUMN tasks.user_id IS '所属用户ID';
COMMENT ON COLUMN tasks.task_type IS '任务类型：main_image=主图生成，detail_page=详情图生成，image_edit=图片编辑';
COMMENT ON COLUMN tasks.status IS '任务状态：pending=待处理，queued=已入队，running=执行中，succeeded=成功，failed=失败，partial_failed=部分失败，cancelled=已取消';
COMMENT ON COLUMN tasks.title IS '任务标题，便于前端展示';
COMMENT ON COLUMN tasks.platform IS '目标平台，例如 taobao、jd、pdd、xhs';
COMMENT ON COLUMN tasks.biz_id IS '业务侧外部ID，可用于和外部系统关联';
COMMENT ON COLUMN tasks.source_task_id IS '来源任务ID，例如编辑任务来源于某个历史生成任务';
COMMENT ON COLUMN tasks.parent_task_id IS '父任务ID，用于表示任务拆分或派生关系';
COMMENT ON COLUMN tasks.current_step IS '当前执行步骤描述';
COMMENT ON COLUMN tasks.progress_percent IS '任务执行进度，范围0到100';
COMMENT ON COLUMN tasks.input_summary IS '输入摘要信息，JSONB格式';
COMMENT ON COLUMN tasks.params IS '任务参数明细，JSONB格式';
COMMENT ON COLUMN tasks.runtime_snapshot IS '运行时快照信息，JSONB格式';
COMMENT ON COLUMN tasks.result_summary IS '结果摘要信息，JSONB格式';
COMMENT ON COLUMN tasks.error_code IS '错误码';
COMMENT ON COLUMN tasks.error_message IS '错误描述';
COMMENT ON COLUMN tasks.retry_count IS '当前任务重试次数';
COMMENT ON COLUMN tasks.started_at IS '任务开始执行时间';
COMMENT ON COLUMN tasks.finished_at IS '任务完成时间';
COMMENT ON COLUMN tasks.created_at IS '创建时间';
COMMENT ON COLUMN tasks.updated_at IS '更新时间';
COMMENT ON COLUMN tasks.deleted_at IS '软删除时间';

CREATE INDEX IF NOT EXISTS idx_tasks_user_created ON tasks(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tasks_user_type_status ON tasks(user_id, task_type, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tasks_status_created ON tasks(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tasks_source_task_id ON tasks(source_task_id);
CREATE INDEX IF NOT EXISTS idx_tasks_parent_task_id ON tasks(parent_task_id);
CREATE INDEX IF NOT EXISTS idx_tasks_params_gin ON tasks USING GIN (params);
CREATE INDEX IF NOT EXISTS idx_tasks_runtime_snapshot_gin ON tasks USING GIN (runtime_snapshot);

CREATE TRIGGER trg_tasks_set_updated_at
BEFORE UPDATE ON tasks
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- =========================================================
-- 6. task_assets 任务素材表
-- =========================================================
CREATE TABLE IF NOT EXISTS task_assets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL,
    user_id UUID NOT NULL,
    role VARCHAR(50) NOT NULL,
    source_type VARCHAR(50) NOT NULL,
    source_task_result_id UUID,
    file_name VARCHAR(255),
    cos_key VARCHAR(500) NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    size_bytes BIGINT NOT NULL,
    sha256 CHAR(64) NOT NULL,
    width INTEGER,
    height INTEGER,
    duration_ms INTEGER,
    scan_status VARCHAR(32) NOT NULL DEFAULT 'pending',
    metadata JSONB,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_task_assets_task_id FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
    CONSTRAINT fk_task_assets_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT ck_task_assets_role CHECK (role IN (
        'main_image_input',
        'detail_input',
        'reference_image',
        'product_image',
        'package_image',
        'detail_result_source',
        'edit_source',
        'edit_mask',
        'edit_annotation',
        'generated_result'
    )),
    CONSTRAINT ck_task_assets_source_type CHECK (source_type IN ('upload', 'task_result', 'system_generated', 'imported')),
    CONSTRAINT ck_task_assets_scan_status CHECK (scan_status IN ('pending', 'passed', 'rejected', 'infected')),
    CONSTRAINT ck_task_assets_size_bytes CHECK (size_bytes >= 0),
    CONSTRAINT ck_task_assets_width CHECK (width IS NULL OR width >= 0),
    CONSTRAINT ck_task_assets_height CHECK (height IS NULL OR height >= 0),
    CONSTRAINT ck_task_assets_duration_ms CHECK (duration_ms IS NULL OR duration_ms >= 0),
    CONSTRAINT ck_task_assets_sort_order CHECK (sort_order >= 0)
);

COMMENT ON TABLE task_assets IS '任务素材表，记录上传素材、参考图、遮罩图、标注图等所有输入资产';
COMMENT ON COLUMN task_assets.id IS '任务素材主键ID';
COMMENT ON COLUMN task_assets.task_id IS '所属任务ID';
COMMENT ON COLUMN task_assets.user_id IS '所属用户ID';
COMMENT ON COLUMN task_assets.role IS '素材角色，例如主图输入图、参考图、编辑遮罩图等';
COMMENT ON COLUMN task_assets.source_type IS '素材来源类型：upload=用户上传，task_result=历史结果复用，system_generated=系统生成，imported=外部导入';
COMMENT ON COLUMN task_assets.source_task_result_id IS '若素材来源于历史任务结果，则关联结果ID';
COMMENT ON COLUMN task_assets.file_name IS '原始文件名';
COMMENT ON COLUMN task_assets.cos_key IS '腾讯云COS对象Key';
COMMENT ON COLUMN task_assets.mime_type IS '素材MIME类型';
COMMENT ON COLUMN task_assets.size_bytes IS '素材文件大小，单位字节';
COMMENT ON COLUMN task_assets.sha256 IS '素材文件SHA256摘要';
COMMENT ON COLUMN task_assets.width IS '图片宽度，单位像素';
COMMENT ON COLUMN task_assets.height IS '图片高度，单位像素';
COMMENT ON COLUMN task_assets.duration_ms IS '媒体时长，单位毫秒，图片通常为空';
COMMENT ON COLUMN task_assets.scan_status IS '安全扫描状态：pending=待扫描，passed=通过，rejected=拒绝，infected=疑似感染';
COMMENT ON COLUMN task_assets.metadata IS '素材附加元数据，JSONB格式';
COMMENT ON COLUMN task_assets.sort_order IS '素材排序序号';
COMMENT ON COLUMN task_assets.created_at IS '创建时间';
COMMENT ON COLUMN task_assets.updated_at IS '更新时间';

CREATE INDEX IF NOT EXISTS idx_task_assets_task_id ON task_assets(task_id);
CREATE INDEX IF NOT EXISTS idx_task_assets_user_id ON task_assets(user_id);
CREATE INDEX IF NOT EXISTS idx_task_assets_role ON task_assets(role);
CREATE INDEX IF NOT EXISTS idx_task_assets_sha256 ON task_assets(sha256);
CREATE INDEX IF NOT EXISTS idx_task_assets_source_task_result_id ON task_assets(source_task_result_id);
CREATE INDEX IF NOT EXISTS idx_task_assets_metadata_gin ON task_assets USING GIN (metadata);

CREATE TRIGGER trg_task_assets_set_updated_at
BEFORE UPDATE ON task_assets
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- =========================================================
-- 7. task_results 任务结果表
-- =========================================================
CREATE TABLE IF NOT EXISTS task_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL,
    user_id UUID NOT NULL,
    result_type VARCHAR(50) NOT NULL,
    page_no INTEGER,
    shot_no INTEGER,
    version_no INTEGER NOT NULL DEFAULT 1,
    parent_result_id UUID,
    status VARCHAR(32) NOT NULL DEFAULT 'succeeded',
    cos_key VARCHAR(500) NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    size_bytes BIGINT NOT NULL,
    sha256 CHAR(64) NOT NULL,
    width INTEGER,
    height INTEGER,
    prompt_plan JSONB,
    prompt_final JSONB,
    render_meta JSONB,
    qc_status VARCHAR(32),
    qc_score NUMERIC(5,2),
    is_primary BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_task_results_task_id FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
    CONSTRAINT fk_task_results_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_task_results_parent_result_id FOREIGN KEY (parent_result_id) REFERENCES task_results(id) ON DELETE SET NULL,
    CONSTRAINT ck_task_results_result_type CHECK (result_type IN ('main_image', 'detail_page', 'edit_result', 'plan_image')),
    CONSTRAINT ck_task_results_status CHECK (status IN ('succeeded', 'failed', 'partial_failed')),
    CONSTRAINT ck_task_results_page_no CHECK (page_no IS NULL OR page_no > 0),
    CONSTRAINT ck_task_results_shot_no CHECK (shot_no IS NULL OR shot_no > 0),
    CONSTRAINT ck_task_results_version_no CHECK (version_no > 0),
    CONSTRAINT ck_task_results_size_bytes CHECK (size_bytes >= 0),
    CONSTRAINT ck_task_results_width CHECK (width IS NULL OR width >= 0),
    CONSTRAINT ck_task_results_height CHECK (height IS NULL OR height >= 0),
    CONSTRAINT ck_task_results_qc_score CHECK (qc_score IS NULL OR (qc_score >= 0 AND qc_score <= 100))
);

COMMENT ON TABLE task_results IS '任务结果表，记录主图、详情图分页结果、编辑结果等所有输出产物';
COMMENT ON COLUMN task_results.id IS '任务结果主键ID';
COMMENT ON COLUMN task_results.task_id IS '所属任务ID';
COMMENT ON COLUMN task_results.user_id IS '所属用户ID';
COMMENT ON COLUMN task_results.result_type IS '结果类型：main_image=主图结果，detail_page=详情图结果，edit_result=编辑结果，plan_image=规划图';
COMMENT ON COLUMN task_results.page_no IS '详情图页码，从1开始';
COMMENT ON COLUMN task_results.shot_no IS '主图序号，从1开始';
COMMENT ON COLUMN task_results.version_no IS '结果版本号，从1开始递增';
COMMENT ON COLUMN task_results.parent_result_id IS '父结果ID，用于记录基于原结果派生的新版本';
COMMENT ON COLUMN task_results.status IS '结果状态：succeeded=成功，failed=失败，partial_failed=部分失败';
COMMENT ON COLUMN task_results.cos_key IS '腾讯云COS对象Key';
COMMENT ON COLUMN task_results.mime_type IS '结果文件MIME类型';
COMMENT ON COLUMN task_results.size_bytes IS '结果文件大小，单位字节';
COMMENT ON COLUMN task_results.sha256 IS '结果文件SHA256摘要';
COMMENT ON COLUMN task_results.width IS '结果图宽度，单位像素';
COMMENT ON COLUMN task_results.height IS '结果图高度，单位像素';
COMMENT ON COLUMN task_results.prompt_plan IS '规划阶段Prompt信息，JSONB格式';
COMMENT ON COLUMN task_results.prompt_final IS '最终生成阶段Prompt信息，JSONB格式';
COMMENT ON COLUMN task_results.render_meta IS '渲染元数据，JSONB格式';
COMMENT ON COLUMN task_results.qc_status IS '质检状态';
COMMENT ON COLUMN task_results.qc_score IS '质检得分，范围0到100';
COMMENT ON COLUMN task_results.is_primary IS '是否为当前任务的主结果';
COMMENT ON COLUMN task_results.created_at IS '创建时间';
COMMENT ON COLUMN task_results.updated_at IS '更新时间';

CREATE INDEX IF NOT EXISTS idx_task_results_task_id ON task_results(task_id);
CREATE INDEX IF NOT EXISTS idx_task_results_user_id ON task_results(user_id);
CREATE INDEX IF NOT EXISTS idx_task_results_parent_result_id ON task_results(parent_result_id);
CREATE INDEX IF NOT EXISTS idx_task_results_task_page ON task_results(task_id, page_no);
CREATE INDEX IF NOT EXISTS idx_task_results_task_shot ON task_results(task_id, shot_no);
CREATE INDEX IF NOT EXISTS idx_task_results_sha256 ON task_results(sha256);
CREATE INDEX IF NOT EXISTS idx_task_results_prompt_plan_gin ON task_results USING GIN (prompt_plan);
CREATE INDEX IF NOT EXISTS idx_task_results_prompt_final_gin ON task_results USING GIN (prompt_final);

CREATE TRIGGER trg_task_results_set_updated_at
BEFORE UPDATE ON task_results
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- 由于 task_assets.source_task_result_id 依赖 task_results，放到此处追加外键
ALTER TABLE task_assets
    ADD CONSTRAINT fk_task_assets_source_task_result_id
    FOREIGN KEY (source_task_result_id) REFERENCES task_results(id) ON DELETE SET NULL;

-- =========================================================
-- 8. task_events 任务事件表
-- =========================================================
CREATE TABLE IF NOT EXISTS task_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL,
    user_id UUID NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    level VARCHAR(20) NOT NULL DEFAULT 'info',
    step VARCHAR(100),
    message TEXT NOT NULL,
    payload JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_task_events_task_id FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
    CONSTRAINT fk_task_events_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT ck_task_events_level CHECK (level IN ('info', 'warn', 'error'))
);

COMMENT ON TABLE task_events IS '任务事件表，记录任务状态流转、步骤日志、失败原因与重要运行事件';
COMMENT ON COLUMN task_events.id IS '任务事件主键ID';
COMMENT ON COLUMN task_events.task_id IS '所属任务ID';
COMMENT ON COLUMN task_events.user_id IS '所属用户ID';
COMMENT ON COLUMN task_events.event_type IS '事件类型，例如 status_changed、step_started、provider_called、result_saved、failed';
COMMENT ON COLUMN task_events.level IS '日志级别：info、warn、error';
COMMENT ON COLUMN task_events.step IS '事件所属执行步骤';
COMMENT ON COLUMN task_events.message IS '事件说明文本';
COMMENT ON COLUMN task_events.payload IS '附加事件数据，JSONB格式';
COMMENT ON COLUMN task_events.created_at IS '创建时间';

CREATE INDEX IF NOT EXISTS idx_task_events_task_id_created ON task_events(task_id, created_at ASC);
CREATE INDEX IF NOT EXISTS idx_task_events_user_id ON task_events(user_id);
CREATE INDEX IF NOT EXISTS idx_task_events_event_type ON task_events(event_type);
CREATE INDEX IF NOT EXISTS idx_task_events_payload_gin ON task_events USING GIN (payload);

-- =========================================================
-- 9. task_usage_records 任务用量记录表
-- =========================================================
CREATE TABLE IF NOT EXISTS task_usage_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL,
    user_id UUID NOT NULL,
    provider_type VARCHAR(50) NOT NULL,
    provider_name VARCHAR(100) NOT NULL,
    model_name VARCHAR(100),
    action_name VARCHAR(100) NOT NULL,
    request_units INTEGER,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    image_count INTEGER,
    latency_ms INTEGER,
    cost_amount NUMERIC(12,4),
    cost_currency VARCHAR(10) NOT NULL DEFAULT 'CNY',
    success BOOLEAN NOT NULL DEFAULT TRUE,
    error_code VARCHAR(100),
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_task_usage_records_task_id FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
    CONSTRAINT fk_task_usage_records_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT ck_task_usage_records_provider_type CHECK (provider_type IN ('llm', 'image', 'ocr', 'bg_remove', 'storage')),
    CONSTRAINT ck_task_usage_records_request_units CHECK (request_units IS NULL OR request_units >= 0),
    CONSTRAINT ck_task_usage_records_prompt_tokens CHECK (prompt_tokens IS NULL OR prompt_tokens >= 0),
    CONSTRAINT ck_task_usage_records_completion_tokens CHECK (completion_tokens IS NULL OR completion_tokens >= 0),
    CONSTRAINT ck_task_usage_records_image_count CHECK (image_count IS NULL OR image_count >= 0),
    CONSTRAINT ck_task_usage_records_latency_ms CHECK (latency_ms IS NULL OR latency_ms >= 0),
    CONSTRAINT ck_task_usage_records_cost_amount CHECK (cost_amount IS NULL OR cost_amount >= 0)
);

COMMENT ON TABLE task_usage_records IS '任务用量记录表，记录模型调用、耗时、成本、图片数量等统计数据';
COMMENT ON COLUMN task_usage_records.id IS '用量记录主键ID';
COMMENT ON COLUMN task_usage_records.task_id IS '所属任务ID';
COMMENT ON COLUMN task_usage_records.user_id IS '所属用户ID';
COMMENT ON COLUMN task_usage_records.provider_type IS '服务提供方类型：llm、image、ocr、bg_remove、storage';
COMMENT ON COLUMN task_usage_records.provider_name IS '服务提供方名称';
COMMENT ON COLUMN task_usage_records.model_name IS '模型名称';
COMMENT ON COLUMN task_usage_records.action_name IS '调用动作名称，例如 planning、render、inpaint';
COMMENT ON COLUMN task_usage_records.request_units IS '请求次数或请求单元数';
COMMENT ON COLUMN task_usage_records.prompt_tokens IS '输入Token数量';
COMMENT ON COLUMN task_usage_records.completion_tokens IS '输出Token数量';
COMMENT ON COLUMN task_usage_records.image_count IS '生成图片数量';
COMMENT ON COLUMN task_usage_records.latency_ms IS '调用耗时，单位毫秒';
COMMENT ON COLUMN task_usage_records.cost_amount IS '成本金额';
COMMENT ON COLUMN task_usage_records.cost_currency IS '成本币种，默认CNY';
COMMENT ON COLUMN task_usage_records.success IS '本次调用是否成功';
COMMENT ON COLUMN task_usage_records.error_code IS '错误码';
COMMENT ON COLUMN task_usage_records.metadata IS '附加统计元数据，JSONB格式';
COMMENT ON COLUMN task_usage_records.created_at IS '创建时间';

CREATE INDEX IF NOT EXISTS idx_task_usage_records_task_id ON task_usage_records(task_id);
CREATE INDEX IF NOT EXISTS idx_task_usage_records_user_id_created ON task_usage_records(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_task_usage_records_provider ON task_usage_records(provider_type, provider_name);
CREATE INDEX IF NOT EXISTS idx_task_usage_records_created_at ON task_usage_records(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_task_usage_records_metadata_gin ON task_usage_records USING GIN (metadata);

-- =========================================================
-- 10. image_edits 图片编辑表
-- =========================================================
CREATE TABLE IF NOT EXISTS image_edits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    result_id UUID NOT NULL,
    task_id UUID NOT NULL,
    user_id UUID NOT NULL,
    mode VARCHAR(50) NOT NULL,
    instruction TEXT NOT NULL,
    annotation_data JSONB,
    mask_cos_key VARCHAR(500),
    source_result_id UUID,
    new_result_id UUID,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_image_edits_result_id FOREIGN KEY (result_id) REFERENCES task_results(id) ON DELETE CASCADE,
    CONSTRAINT fk_image_edits_task_id FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
    CONSTRAINT fk_image_edits_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_image_edits_source_result_id FOREIGN KEY (source_result_id) REFERENCES task_results(id) ON DELETE SET NULL,
    CONSTRAINT fk_image_edits_new_result_id FOREIGN KEY (new_result_id) REFERENCES task_results(id) ON DELETE SET NULL,
    CONSTRAINT ck_image_edits_mode CHECK (mode IN ('rect', 'brush', 'mask', 'fallback_regen')),
    CONSTRAINT ck_image_edits_status CHECK (status IN ('pending', 'queued', 'running', 'succeeded', 'failed', 'cancelled'))
);

COMMENT ON TABLE image_edits IS '图片编辑表，记录单张图片的局部框选、遮罩、编辑指令及新版本生成结果';
COMMENT ON COLUMN image_edits.id IS '图片编辑记录主键ID';
COMMENT ON COLUMN image_edits.result_id IS '当前操作的结果图ID';
COMMENT ON COLUMN image_edits.task_id IS '所属任务ID';
COMMENT ON COLUMN image_edits.user_id IS '所属用户ID';
COMMENT ON COLUMN image_edits.mode IS '编辑模式：rect=矩形选区，brush=画笔遮罩，mask=遮罩图，fallback_regen=受约束全图重生成';
COMMENT ON COLUMN image_edits.instruction IS '用户编辑指令';
COMMENT ON COLUMN image_edits.annotation_data IS '标注数据，JSONB格式，例如矩形框坐标或画笔轨迹';
COMMENT ON COLUMN image_edits.mask_cos_key IS '遮罩图在COS中的对象Key';
COMMENT ON COLUMN image_edits.source_result_id IS '源结果图ID，通常等于原图结果ID';
COMMENT ON COLUMN image_edits.new_result_id IS '编辑成功后生成的新结果图ID';
COMMENT ON COLUMN image_edits.status IS '编辑任务状态：pending、queued、running、succeeded、failed、cancelled';
COMMENT ON COLUMN image_edits.error_message IS '编辑失败时的错误描述';
COMMENT ON COLUMN image_edits.created_at IS '创建时间';
COMMENT ON COLUMN image_edits.updated_at IS '更新时间';

CREATE INDEX IF NOT EXISTS idx_image_edits_result_id ON image_edits(result_id);
CREATE INDEX IF NOT EXISTS idx_image_edits_task_id ON image_edits(task_id);
CREATE INDEX IF NOT EXISTS idx_image_edits_user_id ON image_edits(user_id);
CREATE INDEX IF NOT EXISTS idx_image_edits_new_result_id ON image_edits(new_result_id);
CREATE INDEX IF NOT EXISTS idx_image_edits_annotation_data_gin ON image_edits USING GIN (annotation_data);

CREATE TRIGGER trg_image_edits_set_updated_at
BEFORE UPDATE ON image_edits
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

COMMIT;
