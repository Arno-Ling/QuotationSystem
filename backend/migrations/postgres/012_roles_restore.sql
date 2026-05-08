-- Restore ADMIN role that was accidentally removed
INSERT INTO roles (code, name, description, tenant_type) VALUES
  ('ADMIN',    '管理员', '我方管理员（全部权限）',  'internal'),
  ('OPERATOR', '操作员', '加工方 / 材料方默认角色', 'processor')
ON CONFLICT (code) DO UPDATE SET
  name        = EXCLUDED.name,
  description = EXCLUDED.description,
  tenant_type = EXCLUDED.tenant_type;

SELECT code, name, description, tenant_type FROM roles ORDER BY code;
