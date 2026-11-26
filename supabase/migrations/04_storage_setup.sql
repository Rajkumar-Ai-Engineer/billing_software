-- =============================================================================
-- SRI DHANAM MOTORS - Supabase Storage Configuration
-- Migration: 04_storage_setup.sql
-- Description: Configures the 'shop-assets' bucket for logo, documents, and media.
-- =============================================================================

-- Create storage bucket for shop assets if not exists
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
    'shop-assets', 
    'shop-assets', 
    true, 
    10485760, -- 10MB limit
    ARRAY['image/png', 'image/jpeg', 'image/jpg', 'image/svg+xml', 'application/pdf']
)
ON CONFLICT (id) DO UPDATE SET
    public = true,
    file_size_limit = 10485760;

-- Storage RLS Policies
-- 1. Public Read Policy: Allow anyone to view images/logos
CREATE POLICY "Public Read Shop Assets"
ON storage.objects FOR SELECT
USING (bucket_id = 'shop-assets');

-- 2. Authenticated Upload Policy: Only logged-in users can upload
CREATE POLICY "Authenticated Upload Shop Assets"
ON storage.objects FOR INSERT
TO authenticated
WITH CHECK (bucket_id = 'shop-assets' AND auth.role() = 'authenticated');

-- 3. Authenticated Update Policy
CREATE POLICY "Authenticated Update Shop Assets"
ON storage.objects FOR UPDATE
TO authenticated
USING (bucket_id = 'shop-assets' AND auth.role() = 'authenticated');

-- 4. Authenticated Delete Policy
CREATE POLICY "Authenticated Delete Shop Assets"
ON storage.objects FOR DELETE
TO authenticated
USING (bucket_id = 'shop-assets' AND auth.role() = 'authenticated');
