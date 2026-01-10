-- MaxKB 数据库修复脚本：修正 chunks 列类型
-- 将 chunks 列从 jsonb 改为 character varying[] (字符串数组)

-- 检查并修正 chunks 列类型
DO $$
BEGIN
    -- 检查列是否存在
    IF EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'paragraph' 
        AND column_name = 'chunks'
    ) THEN
        -- 检查当前类型
        IF EXISTS (
            SELECT 1 
            FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = 'paragraph' 
            AND column_name = 'chunks'
            AND data_type = 'jsonb'
        ) THEN
            -- 如果类型是 jsonb，删除并重新创建为 character varying[]
            ALTER TABLE public.paragraph DROP COLUMN chunks;
            ALTER TABLE public.paragraph ADD COLUMN chunks character varying[] DEFAULT ARRAY[]::character varying[];
            RAISE NOTICE '已将 chunks 列从 jsonb 改为 character varying[]';
        ELSIF EXISTS (
            SELECT 1 
            FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = 'paragraph' 
            AND column_name = 'chunks'
            AND udt_name = '_varchar'
        ) THEN
            -- 如果已经是正确的类型，只设置默认值
            ALTER TABLE public.paragraph ALTER COLUMN chunks SET DEFAULT ARRAY[]::character varying[];
            RAISE NOTICE 'chunks 列类型正确，已更新默认值';
        ELSE
            RAISE NOTICE 'chunks 列存在但类型未知，跳过';
        END IF;
    ELSE
        -- 如果列不存在，创建为 character varying[]
        ALTER TABLE public.paragraph 
        ADD COLUMN chunks character varying[] DEFAULT ARRAY[]::character varying[];
        RAISE NOTICE '已添加 chunks 列（character varying[] 类型）';
    END IF;
END $$;

-- 验证列类型
SELECT 
    column_name, 
    data_type,
    udt_name,
    column_default
FROM information_schema.columns 
WHERE table_schema = 'public' 
AND table_name = 'paragraph' 
AND column_name = 'chunks';

