-- =============================================================================
-- Migration 006: 基础数据库 种子数据
-- =============================================================================
-- 作用：给 Stage 2-BASIS 前端页面填充看得到的数据
-- 幂等：全部 ON CONFLICT DO NOTHING
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. material_prices（原料价格）
-- -----------------------------------------------------------------------------
INSERT INTO material_prices (material_code, material_name, spec, unit, unit_price,
                              supplier_id, valid_from, valid_to, source, remark)
VALUES
  ('45#',      '45# 钢',        'φ50x1000',  'kg',   12.50, NULL, '2026-01-01', '2026-12-31', 'manual', '常用中碳钢'),
  ('Cr12MoV',  'Cr12MoV 工具钢','200x100x50','kg',   68.00, NULL, '2026-01-01', '2026-06-30', 'manual', '冷作模具主力材料'),
  ('SKD61',    'SKD61 热作钢',  'φ100x500', 'kg',   95.00, NULL, '2026-01-01', '2026-05-31', 'manual', '压铸模专用'),
  ('S136',     'S136 不锈模具钢','200x150x80','kg', 120.00, NULL, '2026-01-01', '2026-09-30', 'manual', '高镜面/防腐'),
  ('NAK80',    'NAK80 预硬钢',  '250x150x100','kg',  88.00, NULL, '2026-01-01', '2026-12-31', 'manual', '免热处理')
ON CONFLICT (material_code, spec, supplier_id, valid_from) DO NOTHING;


-- -----------------------------------------------------------------------------
-- 2. process_costs（工艺参考价）
-- -----------------------------------------------------------------------------
INSERT INTO process_costs (method_name, supplier_id, cost_type, unit_cost, est_time_hours, valid_from, valid_to, notes)
VALUES
  ('精铣',   NULL, 'per_hour',   80.00, 1.0, '2026-01-01', '2026-12-31', '市场参考价'),
  ('粗铣',   NULL, 'per_hour',   60.00, 1.0, '2026-01-01', '2026-12-31', '市场参考价'),
  ('车',     NULL, 'per_hour',   55.00, 1.0, '2026-01-01', '2026-12-31', '市场参考价'),
  ('钻孔',   NULL, 'per_piece',  15.00, 0.3, '2026-01-01', '2026-12-31', '单孔价'),
  ('磨',     NULL, 'per_hour',   70.00, 1.0, '2026-01-01', '2026-12-31', '平面磨'),
  ('线割',   NULL, 'per_hour',  120.00, 1.0, '2026-01-01', '2026-06-30', '慢丝均价'),
  ('热处理', NULL, 'per_piece', 180.00, NULL,'2026-01-01', '2026-12-31', '淬火回火工艺包'),
  ('表面处理',NULL,'per_piece', 120.00, NULL,'2026-01-01', '2026-12-31', 'PVD 涂层')
ON CONFLICT (method_name, supplier_id, cost_type, valid_from) DO NOTHING;


-- -----------------------------------------------------------------------------
-- 3. equipment_capacity（我方设备台账）
-- -----------------------------------------------------------------------------
INSERT INTO equipment_capacity (equipment_code, equipment_name, method_name,
                                 max_workpiece_dim, precision_grade, daily_hours, notes)
VALUES
  ('CNC-001',  '三轴立式加工中心 VMC850',       '精铣', '800x500x500', 'IT7', 16.0, '日常主力设备'),
  ('CNC-002',  '三轴立式加工中心 VMC1060',      '粗铣', '1000x600x600','IT8', 16.0, ''),
  ('CNC-003',  '五轴加工中心 DMU50',            '精铣', '500x500x350', 'IT6', 16.0, '高精度小件'),
  ('LATHE-01', '数控车 CK6140',                 '车',   'φ400x1000',   'IT7', 16.0, ''),
  ('DRILL-01', '摇臂钻 Z3040',                  '钻孔', 'φ40',         'IT9', 16.0, ''),
  ('GRIND-01', '精密平面磨 M7132',              '磨',   '320x1000',    'IT5', 16.0, '')
ON CONFLICT (equipment_code) DO NOTHING;


-- -----------------------------------------------------------------------------
-- 4. moq_rules（MOQ）
-- -----------------------------------------------------------------------------
INSERT INTO moq_rules (material_code, spec, supplier_id, min_qty, multiple_of, unit, surplus_policy, notes)
VALUES
  ('45#',     'φ50x1000',  NULL, 100, 10, 'kg', 'stock', '常用，超量入库'),
  ('Cr12MoV', '200x100x50',NULL, 50,  5,  'kg', 'stock', '模具钢 MOQ'),
  ('SKD61',   'φ100x500',  NULL, 30,  1,  'kg', 'return','成本高，超量退回')
ON CONFLICT DO NOTHING;


-- -----------------------------------------------------------------------------
-- 5. inventory（示例库存：几条 MOQ 余量）
-- -----------------------------------------------------------------------------
INSERT INTO inventory (material_code, spec, batch_no, qty, unit,
                       inventory_type, status, warehouse_location, remark)
VALUES
  ('45#',     'φ50x1000',   'B2026-001', 25.0, 'kg', 'moq_surplus', 'available', 'A-01', '上次 MOQ 余量'),
  ('Cr12MoV', '200x100x50', 'B2026-002', 12.5, 'kg', 'moq_surplus', 'available', 'A-02', ''),
  ('45#',     'φ50x1000',   'B2025-088', 80.0, 'kg', 'normal',      'available', 'A-01', '常规采购入库')
ON CONFLICT DO NOTHING;


-- -----------------------------------------------------------------------------
-- 校验
-- -----------------------------------------------------------------------------
SELECT 'material_prices'     AS t, COUNT(*) FROM material_prices
UNION ALL SELECT 'process_costs',      COUNT(*) FROM process_costs
UNION ALL SELECT 'equipment_capacity', COUNT(*) FROM equipment_capacity
UNION ALL SELECT 'moq_rules',          COUNT(*) FROM moq_rules
UNION ALL SELECT 'inventory',          COUNT(*) FROM inventory
ORDER BY t;
