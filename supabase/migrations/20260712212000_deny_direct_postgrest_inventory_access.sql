BEGIN;

CREATE POLICY inventory_category_deny_api
    ON public.inventory_category
    FOR ALL TO anon, authenticated
    USING (false)
    WITH CHECK (false);

CREATE POLICY inventory_supplier_deny_api
    ON public.inventory_supplier
    FOR ALL TO anon, authenticated
    USING (false)
    WITH CHECK (false);

CREATE POLICY inventory_product_deny_api
    ON public.inventory_product
    FOR ALL TO anon, authenticated
    USING (false)
    WITH CHECK (false);

CREATE POLICY inventory_lot_deny_api
    ON public.inventory_lot
    FOR ALL TO anon, authenticated
    USING (false)
    WITH CHECK (false);

CREATE POLICY inventory_movement_deny_api
    ON public.inventory_movement
    FOR ALL TO anon, authenticated
    USING (false)
    WITH CHECK (false);

CREATE POLICY inventory_inventorycount_deny_api
    ON public.inventory_inventorycount
    FOR ALL TO anon, authenticated
    USING (false)
    WITH CHECK (false);

CREATE POLICY inventory_inventoryitem_deny_api
    ON public.inventory_inventoryitem
    FOR ALL TO anon, authenticated
    USING (false)
    WITH CHECK (false);

COMMIT;
