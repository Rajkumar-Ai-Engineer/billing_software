-- =============================================================================
-- Sri Dhanam Motors - 06_authorized_users.sql
-- Creates / Updates the three authorized administrator users in Supabase Auth:
--   1. sdmortrs@gmail.com
--   2. muthukumaransuthagar48@gmail.com
--   3. tech84602@gmail.com
-- Default password: dhanam@#123
-- =============================================================================

DO $$
DECLARE
    u_id uuid;
    user_email text;
    user_pwd text := 'dhanam@#123';
    emails text[] := ARRAY['sdmortrs@gmail.com', 'muthukumaransuthagar48@gmail.com', 'tech84602@gmail.com'];
BEGIN
    FOREACH user_email IN ARRAY emails
    LOOP
        SELECT id INTO u_id FROM auth.users WHERE email = user_email;
        
        IF u_id IS NULL THEN
            u_id := gen_random_uuid();
            
            INSERT INTO auth.users (
                instance_id,
                id,
                aud,
                role,
                email,
                encrypted_password,
                email_confirmed_at,
                raw_app_meta_data,
                raw_user_meta_data,
                created_at,
                updated_at,
                is_sso_user,
                is_anonymous,
                confirmation_token,
                recovery_token,
                email_change_token_new,
                email_change,
                email_change_token_current,
                phone_change,
                phone_change_token,
                reauthentication_token
            ) VALUES (
                '00000000-0000-0000-0000-000000000000',
                u_id,
                'authenticated',
                'authenticated',
                user_email,
                extensions.crypt(user_pwd, extensions.gen_salt('bf')),
                NOW(),
                '{"provider": "email", "providers": ["email"]}'::jsonb,
                jsonb_build_object('full_name', 'Sri Dhanam Motors Admin', 'email', user_email),
                NOW(),
                NOW(),
                false,
                false,
                '', '', '', '', '', '', '', ''
            );
            
            INSERT INTO auth.identities (
                id,
                user_id,
                identity_data,
                provider,
                provider_id,
                last_sign_in_at,
                created_at,
                updated_at
            ) VALUES (
                gen_random_uuid(),
                u_id,
                jsonb_build_object('sub', u_id::text, 'email', user_email),
                'email',
                u_id::text,
                NOW(),
                NOW(),
                NOW()
            );
        ELSE
            UPDATE auth.users
            SET encrypted_password = extensions.crypt(user_pwd, extensions.gen_salt('bf')),
                email_confirmed_at = COALESCE(email_confirmed_at, NOW()),
                confirmation_token = COALESCE(confirmation_token, ''),
                recovery_token = COALESCE(recovery_token, ''),
                email_change_token_new = COALESCE(email_change_token_new, ''),
                email_change = COALESCE(email_change, ''),
                email_change_token_current = COALESCE(email_change_token_current, ''),
                phone_change = COALESCE(phone_change, ''),
                phone_change_token = COALESCE(phone_change_token, ''),
                reauthentication_token = COALESCE(reauthentication_token, ''),
                updated_at = NOW()
            WHERE id = u_id;
        END IF;
    END LOOP;
END $$;
