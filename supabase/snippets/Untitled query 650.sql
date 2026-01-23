-- 1. Eliminar las políticas inseguras si las creaste
DROP POLICY IF EXISTS "Users create orgs" ON public.organizations;
DROP POLICY IF EXISTS "Self-insert membership" ON public.organization_members;

-- 2. Asegurar que NADIE (excepto el Backend/Service Role) pueda insertar
-- Al no haber política FOR INSERT, por defecto es DENEGADO para usuarios normales.
-- Esto protege contra spam y auto-asignaciones maliciosas.

-- 3. Mantener (o crear) solo las políticas de LECTURA y EDICIÓN PROPIA

-- Permitir ver organizaciones (Lectura segura)
CREATE POLICY "Users view own orgs" ON public.organizations FOR SELECT USING (
    id IN (SELECT public.get_my_org_ids()) OR type = 'community'
);

-- Permitir a los OWNERS editar SUS organizaciones (Update seguro)
CREATE POLICY "Owners update org" ON public.organizations FOR UPDATE USING (
    id IN (
        SELECT organization_id FROM public.organization_members
        WHERE user_id = auth.uid() AND role = 'owner'
    )
);

-- Permitir ver miembros (Lectura segura)
CREATE POLICY "View team members" ON public.organization_members FOR SELECT USING (
    organization_id IN (SELECT public.get_my_org_ids())
);

-- (Opcional) Si quieres que los owners puedan invitar desde el Frontend directamente:
CREATE POLICY "Owners invite members" ON public.organization_members FOR INSERT
WITH CHECK (
    EXISTS (
        SELECT 1 FROM public.organization_members
        WHERE user_id = auth.uid()
        AND organization_id = public.organization_members.organization_id
        AND role IN ('owner', 'admin')
    )
);
