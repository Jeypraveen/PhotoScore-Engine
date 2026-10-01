-- Atomic Quota Check (Free Tier)
CREATE OR REPLACE FUNCTION consume_check(p_phone text, p_limit int, p_day_start timestamptz)
RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE 
  v_paid boolean; 
  v_used int; 
  v_id bigint;
BEGIN
  -- Prevent concurrent races on the same phone
  PERFORM pg_advisory_xact_lock(hashtext(p_phone));
  
  -- Create user if missing
  INSERT INTO users(phone_number) VALUES (p_phone) ON CONFLICT DO NOTHING;
  
  -- Check paid status
  SELECT coalesce(is_paid AND paid_until > now(), false) INTO v_paid
    FROM users WHERE phone_number = p_phone;
    
  IF NOT v_paid THEN
    SELECT count(*) INTO v_used FROM usage
      WHERE phone_number = p_phone AND used_at >= p_day_start;
    IF v_used >= p_limit THEN 
      RETURN null; 
    END IF;
  END IF;
  
  INSERT INTO usage(phone_number) VALUES (p_phone) RETURNING id INTO v_id;
  RETURN v_id;
END $$;

CREATE INDEX IF NOT EXISTS usage_phone_time ON usage(phone_number, used_at DESC);


-- Atomic Payment Processing
CREATE OR REPLACE FUNCTION apply_payment(p_key text, p_phone text, p_days int)
RETURNS timestamptz LANGUAGE plpgsql AS $$
DECLARE 
  v_until timestamptz;
BEGIN
  -- Deduplicate payment events securely
  INSERT INTO processed_events(id) VALUES (p_key) ON CONFLICT DO NOTHING;
  IF NOT FOUND THEN 
    RETURN null; 
  END IF; -- duplicate delivery

  INSERT INTO users(phone_number) VALUES (p_phone) ON CONFLICT DO NOTHING;
  
  UPDATE users SET is_paid = true,
         paid_until = greatest(coalesce(paid_until, now()), now()) + make_interval(days => p_days)
   WHERE phone_number = p_phone 
   RETURNING paid_until INTO v_until;
   
  RETURN v_until;
END $$;
