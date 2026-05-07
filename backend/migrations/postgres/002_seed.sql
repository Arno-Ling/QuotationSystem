-- =============================================================================
-- 种子数据（weiwai 库）
-- =============================================================================
-- 执行时机：001_schema.sql 跑完后再跑本文件
-- 幂等：全部使用 ON CONFLICT ... DO UPDATE / DO NOTHING
--
-- 账号密码：所有账号统一 test123（bcrypt 哈希已预生成）
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. suppliers（11 家）
-- -----------------------------------------------------------------------------
INSERT INTO suppliers (name, category, address, contact_name, contact_phone) VALUES
  ('青岛和兴嘉业金属制品有限公司', '模架',          '青岛市城阳区棘洪滩街道荣海三路58号',                     '尹总', '13210828919'),
  ('苏州元茂精密机械有限公司',     '全加工零件',    '江苏省苏州市吴江区益堂路与龙桥路交叉口正东方向171米',    '梁总', '18626261708'),
  ('青岛铂锐迪精密机械有限公司',   '全加工零件',    '山东省青岛市即墨区东山前路与富山路交叉口正北方向212米',  '车总', '15253227660'),
  ('昆山宸壮精密模具有限公司',     '全加工零件',    '江苏省苏州市昆山市周市镇宋家港路388号7号厂房',           '蒲总', '15850325668'),
  ('城阳区睿德华模具加工厂',       '快丝/小磨床',   '城阳区靖城路',                                           '白总', '15275256600'),
  ('青岛金源汇精密模具有限公司',   '慢丝',          '青岛东旭包装有限公司山东省青岛市即墨区通济街道圈子村',   '陈总', '18953281706'),
  ('青岛铭微德精密机械有限公司',   '沙迪克慢丝',    '山东省青岛市城阳区百福路185号',                         '刘总', '13325000740'),
  ('宁波市百德模具有限公司',       '全加工零件',    '慈溪市周巷镇周东三角站南300米',                         '刘总', '13515746239'),
  ('昆山市卓诚辉电子科技有限公司', '全加工零件',    '江苏省苏州市昆山市太湖北路998号',                       '陈总', '13879304042'),
  ('青岛颖泰和精密机械有限公司',   '钣金',          '山东省青岛市即墨区龙山办事处后北葛工业园204国道旁',     '陈总', '18265328979'),
  ('青岛华欣泽机械模具有限公司',   '快丝/中丝/慢丝','山东省青岛市即墨区淮涉河三路312号南60米',                '金总', '13792460522')
ON CONFLICT (name) DO UPDATE SET
  category      = EXCLUDED.category,
  address       = EXCLUDED.address,
  contact_name  = EXCLUDED.contact_name,
  contact_phone = EXCLUDED.contact_phone;


-- -----------------------------------------------------------------------------
-- 2. tenants（1 内部 + 2 加工方）
-- -----------------------------------------------------------------------------
INSERT INTO tenants (tenant_type, name, supplier_id, contact_name, contact_phone) VALUES
  ('internal',  '我方-模具制造厂',             NULL,                                                             'Alice', '13800000001'),
  ('processor', '青岛华欣泽机械模具有限公司', (SELECT id FROM suppliers WHERE name='青岛华欣泽机械模具有限公司'), '金总',  '13792460522'),
  ('processor', '苏州元茂精密机械有限公司',   (SELECT id FROM suppliers WHERE name='苏州元茂精密机械有限公司'),   '梁总',  '18626261708')
ON CONFLICT (name) DO UPDATE SET
  tenant_type   = EXCLUDED.tenant_type,
  supplier_id   = EXCLUDED.supplier_id,
  contact_name  = EXCLUDED.contact_name,
  contact_phone = EXCLUDED.contact_phone;


-- -----------------------------------------------------------------------------
-- 3. users（密码统一 test123）
-- -----------------------------------------------------------------------------
-- bcrypt($2b$12$, cost=12) hash of plaintext "test123"
INSERT INTO users (tenant_id, username, password_hash, display_name, role, is_active) VALUES
  ((SELECT id FROM tenants WHERE name='我方-模具制造厂'),             'alice',    '$2b$12$tlvx8/TCrANPZ66qSIy8m./pw8yN6PgJ0dKRzhMD3kLk69/fnjXNi', 'Alice（管理员/采购）', 'admin',              TRUE),
  ((SELECT id FROM tenants WHERE name='我方-模具制造厂'),             'bob',      '$2b$12$tlvx8/TCrANPZ66qSIy8m./pw8yN6PgJ0dKRzhMD3kLk69/fnjXNi', 'Bob（生产经理）',      'production_manager', TRUE),
  ((SELECT id FROM tenants WHERE name='我方-模具制造厂'),             'carol',    '$2b$12$tlvx8/TCrANPZ66qSIy8m./pw8yN6PgJ0dKRzhMD3kLk69/fnjXNi', 'Carol（采购经理）',    'purchasing_manager', TRUE),
  ((SELECT id FROM tenants WHERE name='青岛华欣泽机械模具有限公司'),  'huaxinze', '$2b$12$tlvx8/TCrANPZ66qSIy8m./pw8yN6PgJ0dKRzhMD3kLk69/fnjXNi', '华欣泽-金总',          'operator',           TRUE),
  ((SELECT id FROM tenants WHERE name='苏州元茂精密机械有限公司'),    'yuanmao',  '$2b$12$tlvx8/TCrANPZ66qSIy8m./pw8yN6PgJ0dKRzhMD3kLk69/fnjXNi', '元茂-梁总',            'operator',           TRUE)
ON CONFLICT (username) DO UPDATE SET
  tenant_id     = EXCLUDED.tenant_id,
  password_hash = EXCLUDED.password_hash,
  display_name  = EXCLUDED.display_name,
  role          = EXCLUDED.role,
  is_active     = TRUE;


-- -----------------------------------------------------------------------------
-- 4. supplier_capabilities（工艺能力标签）
-- -----------------------------------------------------------------------------
INSERT INTO supplier_capabilities (supplier_id, process_name)
SELECT s.id, p.proc
FROM (VALUES
  ('青岛和兴嘉业金属制品有限公司', '模架'),
  ('苏州元茂精密机械有限公司',     '全加工零件'),
  ('苏州元茂精密机械有限公司',     '磨'),
  ('苏州元茂精密机械有限公司',     '铣'),
  ('苏州元茂精密机械有限公司',     '车'),
  ('青岛铂锐迪精密机械有限公司',   '全加工零件'),
  ('青岛铂锐迪精密机械有限公司',   '磨'),
  ('青岛铂锐迪精密机械有限公司',   '铣'),
  ('青岛铂锐迪精密机械有限公司',   '车'),
  ('昆山宸壮精密模具有限公司',     '全加工零件'),
  ('昆山宸壮精密模具有限公司',     '磨'),
  ('昆山宸壮精密模具有限公司',     '铣'),
  ('昆山宸壮精密模具有限公司',     '车'),
  ('城阳区睿德华模具加工厂',       '快丝'),
  ('城阳区睿德华模具加工厂',       '小磨床'),
  ('城阳区睿德华模具加工厂',       '磨'),
  ('青岛金源汇精密模具有限公司',   '慢丝'),
  ('青岛金源汇精密模具有限公司',   '线割'),
  ('青岛铭微德精密机械有限公司',   '慢丝'),
  ('青岛铭微德精密机械有限公司',   '线割'),
  ('宁波市百德模具有限公司',       '全加工零件'),
  ('宁波市百德模具有限公司',       '磨'),
  ('宁波市百德模具有限公司',       '铣'),
  ('宁波市百德模具有限公司',       '车'),
  ('昆山市卓诚辉电子科技有限公司', '全加工零件'),
  ('青岛颖泰和精密机械有限公司',   '钣金'),
  ('青岛华欣泽机械模具有限公司',   '快丝'),
  ('青岛华欣泽机械模具有限公司',   '中丝'),
  ('青岛华欣泽机械模具有限公司',   '慢丝'),
  ('青岛华欣泽机械模具有限公司',   '线割'),
  ('青岛华欣泽机械模具有限公司',   '热处理'),
  ('青岛华欣泽机械模具有限公司',   '表面处理')
) AS p(sup_name, proc)
JOIN suppliers s ON s.name = p.sup_name
ON CONFLICT (supplier_id, process_name) DO NOTHING;


-- =============================================================================
-- 完成校验
-- =============================================================================
SELECT 'suppliers'              AS table_name, COUNT(*) AS row_count FROM suppliers
UNION ALL
SELECT 'tenants',               COUNT(*) FROM tenants
UNION ALL
SELECT 'users',                 COUNT(*) FROM users
UNION ALL
SELECT 'supplier_capabilities', COUNT(*) FROM supplier_capabilities
ORDER BY table_name;
-- 期望：
--   supplier_capabilities   32
--   suppliers               11
--   tenants                  3
--   users                    5
