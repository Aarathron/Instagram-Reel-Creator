

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;


CREATE EXTENSION IF NOT EXISTS "pg_cron" WITH SCHEMA "pg_catalog";






CREATE EXTENSION IF NOT EXISTS "pgsodium";






COMMENT ON SCHEMA "public" IS 'standard public schema';



CREATE EXTENSION IF NOT EXISTS "pg_graphql" WITH SCHEMA "graphql";






CREATE EXTENSION IF NOT EXISTS "pg_stat_statements" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "pgcrypto" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "pgjwt" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "supabase_vault" WITH SCHEMA "vault";






CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA "extensions";






CREATE TYPE "public"."b2c_order_status" AS ENUM (
    'order_placed',
    'pending_payment',
    'gathering_info',
    'writing_lyrics',
    'lyrics_review',
    'song_production',
    'completed',
    'cancelled',
    'song_submitted'
);


ALTER TYPE "public"."b2c_order_status" OWNER TO "postgres";


CREATE TYPE "public"."b2c_package_type" AS ENUM (
    'quick',
    'premium',
    'ultimate'
);


ALTER TYPE "public"."b2c_package_type" OWNER TO "postgres";


CREATE TYPE "public"."b2c_revision_status" AS ENUM (
    'requested',
    'in_progress',
    'completed'
);


ALTER TYPE "public"."b2c_revision_status" OWNER TO "postgres";


CREATE TYPE "public"."b2c_song_status" AS ENUM (
    'pending',
    'lyrics_generation',
    'recording',
    'mixing',
    'completed'
);


ALTER TYPE "public"."b2c_song_status" OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."b2c_update_modified_column"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
BEGIN
   NEW.updated_at = now();
   RETURN NEW;
END;
$$;


ALTER FUNCTION "public"."b2c_update_modified_column"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."daily_update_birthdays"() RETURNS "void"
    LANGUAGE "plpgsql"
    AS $$
BEGIN
    UPDATE Employees
    SET 
        upcoming_birthday = CASE 
            WHEN TO_DATE(TO_CHAR(DOB, 'MM-DD'), 'MM-DD') >= TO_DATE(TO_CHAR(CURRENT_DATE, 'MM-DD'), 'MM-DD')
            THEN TO_DATE(TO_CHAR(EXTRACT(YEAR FROM CURRENT_DATE), '0000') || '-' || TO_CHAR(DOB, 'MM-DD'), 'YYYY-MM-DD')
            ELSE TO_DATE(TO_CHAR(EXTRACT(YEAR FROM CURRENT_DATE) + 1, '0000') || '-' || TO_CHAR(DOB, 'MM-DD'), 'YYYY-MM-DD')
        END,
        days_until_birthday = CASE 
            WHEN TO_DATE(TO_CHAR(DOB, 'MM-DD'), 'MM-DD') >= TO_DATE(TO_CHAR(CURRENT_DATE, 'MM-DD'), 'MM-DD')
            THEN TO_DATE(TO_CHAR(EXTRACT(YEAR FROM CURRENT_DATE), '0000') || '-' || TO_CHAR(DOB, 'MM-DD'), 'YYYY-MM-DD') - CURRENT_DATE
            ELSE TO_DATE(TO_CHAR(EXTRACT(YEAR FROM CURRENT_DATE) + 1, '0000') || '-' || TO_CHAR(DOB, 'MM-DD'), 'YYYY-MM-DD') - CURRENT_DATE
        END;
END;
$$;


ALTER FUNCTION "public"."daily_update_birthdays"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."get_connect_worthy_contacts"() RETURNS TABLE("employee_id" bigint, "employee_name" "text", "birthday_information_id" bigint, "birthday_employee_id" bigint)
    LANGUAGE "plpgsql"
    AS $$
BEGIN
    RETURN QUERY
    SELECT 
        e.employee_id,
        e.employee_name,
        b.id AS birthday_information_id,
        b.birthday_employee AS birthday_employee_id
    FROM 
        birthday_information_gathering b
    JOIN 
        employees e
    ON 
        b.respondent_employee = e.employee_id
    WHERE 
        b.status = 'contacted' AND
        (
            b.last_sent_conversation_time IS NULL OR 
            b.last_sent_conversation_time < NOW() - INTERVAL '6 hours'
        ) AND
        b.reminder_count < 4;
END;
$$;


ALTER FUNCTION "public"."get_connect_worthy_contacts"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."get_employee_and_birthday_info"("input_phone" "text") RETURNS TABLE("employee_id" bigint, "employee_name" "text", "birthday_information_id" bigint, "birthday_employee_id" bigint)
    LANGUAGE "plpgsql"
    AS $$
BEGIN
    RETURN QUERY
    SELECT 
        e.employee_id,
        e.employee_name,
        b.id AS birthday_information_id,
        b.birthday_employee AS birthday_employee_id
    FROM 
        employees e
    JOIN 
        birthday_information_gathering b
    ON 
        e.employee_id = b.respondent_employee
    WHERE 
        CONCAT(e.country_code, e.phone_number) = input_phone;
END;
$$;


ALTER FUNCTION "public"."get_employee_and_birthday_info"("input_phone" "text") OWNER TO "postgres";

SET default_tablespace = '';

SET default_table_access_method = "heap";


CREATE TABLE IF NOT EXISTS "public"."employees" (
    "employee_id" bigint NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "company_employee_id" "text" NOT NULL,
    "company_id" bigint,
    "employee_name" "text",
    "gender" "text",
    "dob" "date",
    "designation" "text",
    "department" "text",
    "doj" "date",
    "profile_pic" "text",
    "reporting_manager_id" "text",
    "location" "text",
    "upcoming_birthday" "date",
    "days_until_birthday" integer,
    "is_birthday_soon" boolean DEFAULT false,
    "birthday_mail_sent" boolean DEFAULT false,
    "phone_number" "text",
    "country_code" "text",
    "status" "text" DEFAULT 'CLOSED'::"text"
);


ALTER TABLE "public"."employees" OWNER TO "postgres";


COMMENT ON TABLE "public"."employees" IS 'This table holds all the information about the employees';



CREATE OR REPLACE FUNCTION "public"."get_related_employees"("p_employee_id" integer) RETURNS SETOF "public"."employees"
    LANGUAGE "plpgsql"
    AS $$
DECLARE
  emp_record employees%ROWTYPE;
BEGIN
  ------------------------------------------------------------------
  -- 1) Fetch the row for the target employee
  ------------------------------------------------------------------
  SELECT *
    INTO emp_record
    FROM employees
   WHERE employee_id = p_employee_id;
   
  IF NOT FOUND THEN
    -- No such employee => return empty
    RETURN;
  END IF;

  ------------------------------------------------------------------
  -- 2) If no manager, return all employees in the same company
  --    EXCEPT this employee
  ------------------------------------------------------------------
  IF emp_record.reporting_manager_id IS NULL
     OR emp_record.reporting_manager_id = '' THEN
    
    RETURN QUERY
    SELECT *
      FROM employees
     WHERE company_id   = emp_record.company_id
       AND employee_id <> p_employee_id;

    RETURN;  -- Stop here
  END IF;

  ------------------------------------------------------------------
  -- 3) Return the manager (if exists)
  ------------------------------------------------------------------
  RETURN QUERY
  SELECT *
    FROM employees
   WHERE company_employee_id = emp_record.reporting_manager_id
     AND company_id          = emp_record.company_id
   LIMIT 1;

  ------------------------------------------------------------------
  -- 4) Return the colleagues (same manager, excluding this employee)
  ------------------------------------------------------------------
  RETURN QUERY
  SELECT *
    FROM employees
   WHERE reporting_manager_id = emp_record.reporting_manager_id
     AND company_id           = emp_record.company_id
     AND employee_id         <> emp_record.employee_id;

  ------------------------------------------------------------------
  -- 5) Return the subordinates (employees who report to this employee)
  ------------------------------------------------------------------
  RETURN QUERY
  SELECT *
    FROM employees
   WHERE reporting_manager_id = emp_record.company_employee_id
     AND company_id           = emp_record.company_id;

  ------------------------------------------------------------------
  -- End of function
  ------------------------------------------------------------------
END;
$$;


ALTER FUNCTION "public"."get_related_employees"("p_employee_id" integer) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."get_total_employees"("company_id_input" integer) RETURNS "json"
    LANGUAGE "plpgsql"
    AS $$
DECLARE
    total_employees INT;
BEGIN
    -- Count the number of employees for the given company_id
    SELECT COUNT(*)
    INTO total_employees
    FROM employees
    WHERE company_id = company_id_input;

    -- Return the result as JSON
    RETURN json_build_object('total_employees', total_employees);
END;
$$;


ALTER FUNCTION "public"."get_total_employees"("company_id_input" integer) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."handle_new_user"() RETURNS "trigger"
    LANGUAGE "plpgsql" SECURITY DEFINER
    AS $$
begin
  insert into public.b2c_profiles (id, email, full_name, created_at, updated_at)
  values (new.id, new.email, new.raw_user_meta_data->>'name', now(), now());
  return new;
end;
$$;


ALTER FUNCTION "public"."handle_new_user"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."trigger_update_employee_birthdays"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
BEGIN
    -- Calculate upcoming_birthday
    NEW.upcoming_birthday := CASE 
        WHEN TO_DATE(TO_CHAR(NEW.dob, 'MM-DD'), 'MM-DD') >= TO_DATE(TO_CHAR(CURRENT_DATE, 'MM-DD'), 'MM-DD')
        THEN TO_DATE(TO_CHAR(EXTRACT(YEAR FROM CURRENT_DATE), '0000') || '-' || TO_CHAR(NEW.dob, 'MM-DD'), 'YYYY-MM-DD')
        ELSE TO_DATE(TO_CHAR(EXTRACT(YEAR FROM CURRENT_DATE) + 1, '0000') || '-' || TO_CHAR(NEW.dob, 'MM-DD'), 'YYYY-MM-DD')
    END;

    -- Calculate days_until_birthday
    NEW.days_until_birthday := CASE 
        WHEN TO_DATE(TO_CHAR(NEW.dob, 'MM-DD'), 'MM-DD') >= TO_DATE(TO_CHAR(CURRENT_DATE, 'MM-DD'), 'MM-DD')
        THEN TO_DATE(TO_CHAR(EXTRACT(YEAR FROM CURRENT_DATE), '0000') || '-' || TO_CHAR(NEW.dob, 'MM-DD'), 'YYYY-MM-DD') - CURRENT_DATE
        ELSE TO_DATE(TO_CHAR(EXTRACT(YEAR FROM CURRENT_DATE) + 1, '0000') || '-' || TO_CHAR(NEW.dob, 'MM-DD'), 'YYYY-MM-DD') - CURRENT_DATE
    END;

    -- Set is_birthday_soon
    NEW.is_birthday_soon := (NEW.days_until_birthday < 15);

    RETURN NEW;
END;
$$;


ALTER FUNCTION "public"."trigger_update_employee_birthdays"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."update_b2c_orders_status"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$BEGIN
  -- Update the status of the order if it exists
  UPDATE b2c_orders
    SET status = 'gathering_info'
  WHERE id = NEW.order_id;  -- Make sure "id" in b2c_orders matches the "order_id" in b2c_payments

  -- Return the newly inserted row to finalize
  RETURN NEW;
END;$$;


ALTER FUNCTION "public"."update_b2c_orders_status"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."update_b2c_profiles_uid"() RETURNS "trigger"
    LANGUAGE "plpgsql" SECURITY DEFINER
    AS $$
begin
  update public.b2c_profiles
  set id = new.id
  where email = new.email;
  return new;
end;
$$;


ALTER FUNCTION "public"."update_b2c_profiles_uid"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."update_birthday_fields"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
BEGIN
    -- Calculate upcoming_birthday
    NEW.upcoming_birthday := 
        CASE 
            WHEN TO_DATE(TO_CHAR(NEW.DOB, 'MM-DD'), 'MM-DD') >= TO_DATE(TO_CHAR(CURRENT_DATE, 'MM-DD'), 'MM-DD')
            THEN TO_DATE(TO_CHAR(EXTRACT(YEAR FROM CURRENT_DATE), '0000') || '-' || TO_CHAR(NEW.DOB, 'MM-DD'), 'YYYY-MM-DD')
            ELSE TO_DATE(TO_CHAR(EXTRACT(YEAR FROM CURRENT_DATE) + 1, '0000') || '-' || TO_CHAR(NEW.DOB, 'MM-DD'), 'YYYY-MM-DD')
        END;

    -- Calculate days_until_birthday
    NEW.days_until_birthday := 
        CASE 
            WHEN TO_DATE(TO_CHAR(NEW.DOB, 'MM-DD'), 'MM-DD') >= TO_DATE(TO_CHAR(CURRENT_DATE, 'MM-DD'), 'MM-DD')
            THEN TO_DATE(TO_CHAR(EXTRACT(YEAR FROM CURRENT_DATE), '0000') || '-' || TO_CHAR(NEW.DOB, 'MM-DD'), 'YYYY-MM-DD') - CURRENT_DATE
            ELSE TO_DATE(TO_CHAR(EXTRACT(YEAR FROM CURRENT_DATE) + 1, '0000') || '-' || TO_CHAR(NEW.DOB, 'MM-DD'), 'YYYY-MM-DD') - CURRENT_DATE
        END;

    RETURN NEW;
END;
$$;


ALTER FUNCTION "public"."update_birthday_fields"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."update_employee_birthdays"() RETURNS "void"
    LANGUAGE "plpgsql"
    AS $$
BEGIN
    UPDATE employees
    SET 
        upcoming_birthday = CASE 
            WHEN TO_DATE(TO_CHAR(dob, 'MM-DD'), 'MM-DD') >= TO_DATE(TO_CHAR(CURRENT_DATE, 'MM-DD'), 'MM-DD')
            THEN TO_DATE(TO_CHAR(EXTRACT(YEAR FROM CURRENT_DATE), '0000') || '-' || TO_CHAR(dob, 'MM-DD'), 'YYYY-MM-DD')
            ELSE TO_DATE(TO_CHAR(EXTRACT(YEAR FROM CURRENT_DATE) + 1, '0000') || '-' || TO_CHAR(dob, 'MM-DD'), 'YYYY-MM-DD')
        END,
        days_until_birthday = CASE 
            WHEN TO_DATE(TO_CHAR(dob, 'MM-DD'), 'MM-DD') >= TO_DATE(TO_CHAR(CURRENT_DATE, 'MM-DD'), 'MM-DD')
            THEN TO_DATE(TO_CHAR(EXTRACT(YEAR FROM CURRENT_DATE), '0000') || '-' || TO_CHAR(dob, 'MM-DD'), 'YYYY-MM-DD') - CURRENT_DATE
            ELSE TO_DATE(TO_CHAR(EXTRACT(YEAR FROM CURRENT_DATE) + 1, '0000') || '-' || TO_CHAR(dob, 'MM-DD'), 'YYYY-MM-DD') - CURRENT_DATE
        END,
        is_birthday_soon = (CASE 
            WHEN TO_DATE(TO_CHAR(dob, 'MM-DD'), 'MM-DD') >= TO_DATE(TO_CHAR(CURRENT_DATE, 'MM-DD'), 'MM-DD')
            THEN TO_DATE(TO_CHAR(EXTRACT(YEAR FROM CURRENT_DATE), '0000') || '-' || TO_CHAR(dob, 'MM-DD'), 'YYYY-MM-DD') - CURRENT_DATE < 15
            ELSE TO_DATE(TO_CHAR(EXTRACT(YEAR FROM CURRENT_DATE) + 1, '0000') || '-' || TO_CHAR(dob, 'MM-DD'), 'YYYY-MM-DD') - CURRENT_DATE < 15
        END);
END;
$$;


ALTER FUNCTION "public"."update_employee_birthdays"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."update_is_recent"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
BEGIN
  NEW.is_recent := (
    NEW.last_message_received_time >= NOW() - INTERVAL '24 hours'
  );
  RETURN NEW;
END;
$$;


ALTER FUNCTION "public"."update_is_recent"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."update_is_recent_status"() RETURNS "void"
    LANGUAGE "plpgsql"
    AS $$
BEGIN
  UPDATE b2c_interactions_customers
  SET is_recent = (
    last_message_received_time >= NOW() - INTERVAL '24 hours'
  );
END;
$$;


ALTER FUNCTION "public"."update_is_recent_status"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."update_last_message_received"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
BEGIN
  -- Update the contact record's last_message_received_at with the current
  -- message's timestamp (assuming `created_at` is the column storing message time).

  UPDATE b2c_whatsapp_contacts
    SET last_message_received_at = NEW.created_at,
    last_message_content = NEW.message
    WHERE wa_id = NEW.wa_id;

  -- Return the new row so the insert continues as normal.
  RETURN NEW;
END;
$$;


ALTER FUNCTION "public"."update_last_message_received"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."upsert_order_details"("p_order_id" "uuid", "p_recipient_name" "text", "p_relationship" "text", "p_occasion" "text", "p_language" "text", "p_mood" "text", "p_vocals" "text", "p_additional_info" "text") RETURNS "uuid"
    LANGUAGE "plpgsql" SECURITY DEFINER
    AS $$
DECLARE
  existing_id UUID;
  result_id UUID;
BEGIN
  -- Check if a record already exists
  SELECT id INTO existing_id FROM public.b2c_order_details
  WHERE order_id = p_order_id;
  
  IF existing_id IS NOT NULL THEN
    -- Update existing record
    UPDATE public.b2c_order_details
    SET 
      recipient_name = p_recipient_name,
      relationship = p_relationship,
      occasion = p_occasion,
      language = p_language,
      mood = p_mood,
      vocals = p_vocals,
      additional_info = p_additional_info
    WHERE id = existing_id;
    
    result_id := existing_id;
  ELSE
    -- Insert new record
    INSERT INTO public.b2c_order_details (
      order_id, recipient_name, relationship, occasion, 
      language, mood, vocals, additional_info
    ) VALUES (
      p_order_id, p_recipient_name, p_relationship, p_occasion,
      p_language, p_mood, p_vocals, p_additional_info
    )
    RETURNING id INTO result_id;
  END IF;
  
  RETURN result_id;
END;
$$;


ALTER FUNCTION "public"."upsert_order_details"("p_order_id" "uuid", "p_recipient_name" "text", "p_relationship" "text", "p_occasion" "text", "p_language" "text", "p_mood" "text", "p_vocals" "text", "p_additional_info" "text") OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."b2c_chat_messages" (
    "id" "uuid" DEFAULT "extensions"."uuid_generate_v4"() NOT NULL,
    "session_id" "uuid" NOT NULL,
    "is_user" boolean NOT NULL,
    "content" "text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"(),
    "metadata" "jsonb"
);


ALTER TABLE "public"."b2c_chat_messages" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."b2c_chat_sessions" (
    "id" "uuid" DEFAULT "extensions"."uuid_generate_v4"() NOT NULL,
    "user_id" "uuid" NOT NULL,
    "order_id" "uuid",
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"(),
    "is_active" boolean DEFAULT true
);


ALTER TABLE "public"."b2c_chat_sessions" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."b2c_customers" (
    "id" bigint NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "name" "text",
    "wa_id" "text",
    "occasion" "text",
    "status" "text",
    "phone_number" "text",
    "countrycode" "text",
    "gathering_data_started_at" timestamp with time zone,
    "detailed_summary_of_information" "jsonb",
    "song_details" "jsonb",
    "text summary" "text",
    "final_lyrics" "text",
    "transaction_closed" boolean DEFAULT false NOT NULL,
    "count_of_songs" smallint DEFAULT '0'::smallint
);


ALTER TABLE "public"."b2c_customers" OWNER TO "postgres";


ALTER TABLE "public"."b2c_customers" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."b2c_customers_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."b2c_error_logs" (
    "id" "uuid" DEFAULT "extensions"."uuid_generate_v4"() NOT NULL,
    "error_type" "text" NOT NULL,
    "order_id" "uuid",
    "error_message" "text",
    "error_details" "text",
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."b2c_error_logs" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."b2c_image_creations_duplicate" (
    "id" bigint NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "wa_id" "text",
    "piApi_task_id" "text",
    "status" "text",
    "sent_to_user" boolean,
    "customer_name" "text",
    "onedrive_folder_id" "text",
    "model" "text"
);


ALTER TABLE "public"."b2c_image_creations_duplicate" OWNER TO "postgres";


COMMENT ON TABLE "public"."b2c_image_creations_duplicate" IS 'This is a duplicate of b2c_song_creations';



ALTER TABLE "public"."b2c_image_creations_duplicate" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."b2c_image_creations_duplicate_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."b2c_interactions_customers" (
    "id" bigint NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "wa_id" "text",
    "Name" "text",
    "important_details" "jsonb",
    "status" "text",
    "last_message_received_time" timestamp with time zone,
    "is_recent" boolean,
    "last_self_sent_message" timestamp with time zone,
    "samples_sent" boolean DEFAULT false,
    "is_payment_done" boolean DEFAULT false,
    "next_connectTime" timestamp with time zone,
    "reminder_count" smallint DEFAULT '0'::smallint,
    "STOP" "text",
    "reconnected" boolean DEFAULT false
);


ALTER TABLE "public"."b2c_interactions_customers" OWNER TO "postgres";


ALTER TABLE "public"."b2c_interactions_customers" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."b2c_interactions_customers_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."b2c_lyrics" (
    "id" "uuid" DEFAULT "extensions"."uuid_generate_v4"() NOT NULL,
    "order_id" "uuid" NOT NULL,
    "content" "text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"(),
    "created_by" "text" DEFAULT 'ai_system'::"text",
    "is_approved" boolean DEFAULT false,
    "approved_at" timestamp with time zone,
    "version" integer DEFAULT 1,
    "feedback_notes" "text"
);


ALTER TABLE "public"."b2c_lyrics" OWNER TO "postgres";


COMMENT ON COLUMN "public"."b2c_lyrics"."created_by" IS 'Source of the lyrics: "ai" for AI-generated, "user" for user edits';



CREATE TABLE IF NOT EXISTS "public"."b2c_order_details" (
    "id" "uuid" DEFAULT "extensions"."uuid_generate_v4"() NOT NULL,
    "order_id" "uuid" NOT NULL,
    "recipient_name" "text" NOT NULL,
    "relationship" "text",
    "recipient_age" "text",
    "occasion" "text" NOT NULL,
    "event_date" "date",
    "language" "text" NOT NULL,
    "mood" "text" NOT NULL,
    "vocals" "text" DEFAULT 'female'::"text",
    "additional_info" "text"
);


ALTER TABLE "public"."b2c_order_details" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."b2c_orders" (
    "id" "uuid" DEFAULT "extensions"."uuid_generate_v4"() NOT NULL,
    "user_id" "uuid" NOT NULL,
    "package_type" "public"."b2c_package_type" NOT NULL,
    "express_delivery" boolean DEFAULT false,
    "total_amount" numeric(10,2) NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"(),
    "estimated_delivery_at" timestamp with time zone,
    "payment_id" "uuid",
    "lyrics_available_at" timestamp with time zone,
    "lyrics_generation_queued" boolean DEFAULT false,
    "dedication_started_at" timestamp with time zone,
    "payment_completed_at" timestamp with time zone,
    "status" "public"."b2c_order_status" DEFAULT 'order_placed'::"public"."b2c_order_status"
);


ALTER TABLE "public"."b2c_orders" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."b2c_payments" (
    "id" "uuid" DEFAULT "extensions"."uuid_generate_v4"() NOT NULL,
    "order_id" "uuid" NOT NULL,
    "amount" numeric(10,2) NOT NULL,
    "currency" "text" DEFAULT 'INR'::"text",
    "payment_method" "text",
    "payment_gateway" "text" DEFAULT 'razorpay'::"text",
    "payment_gateway_id" "text",
    "status" "text",
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."b2c_payments" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."b2c_profiles" (
    "id" "uuid" NOT NULL,
    "email" "text" NOT NULL,
    "full_name" "text",
    "phone" "text",
    "country_code" "text" DEFAULT '+91'::"text",
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."b2c_profiles" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."b2c_recipient_info" (
    "id" "uuid" DEFAULT "extensions"."uuid_generate_v4"() NOT NULL,
    "order_id" "uuid" NOT NULL,
    "name" "text",
    "relationship" "text",
    "traits" "text"[],
    "stories" "text"[],
    "interests" "text"[],
    "achievements" "text"[],
    "memories" "text"[],
    "summary" "text",
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"(),
    "message" "text",
    "completion_status" integer DEFAULT 0
);


ALTER TABLE "public"."b2c_recipient_info" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."b2c_revisions" (
    "id" "uuid" DEFAULT "extensions"."uuid_generate_v4"() NOT NULL,
    "order_id" "uuid" NOT NULL,
    "requested_by" "uuid" NOT NULL,
    "notes" "text" NOT NULL,
    "status" "public"."b2c_revision_status" DEFAULT 'requested'::"public"."b2c_revision_status",
    "created_at" timestamp with time zone DEFAULT "now"(),
    "completed_at" timestamp with time zone
);


ALTER TABLE "public"."b2c_revisions" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."b2c_samples" (
    "id" bigint NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "occasion" "text",
    "language" "text",
    "download_url" "text",
    "singer" "text",
    "relationship" "text",
    "Title" "text"
);


ALTER TABLE "public"."b2c_samples" OWNER TO "postgres";


ALTER TABLE "public"."b2c_samples" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."b2c_samples_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."b2c_song_creations" (
    "id" bigint NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "wa_id" "text",
    "song_id" "text",
    "status" "text",
    "tags" "text",
    "lyrics" "text",
    "sent_to_user" boolean,
    "audio_url" "text",
    "customer_name" "text",
    "onedrive_folder_id" "text",
    "song_duration" double precision,
    "upload_type" "text"
);


ALTER TABLE "public"."b2c_song_creations" OWNER TO "postgres";


ALTER TABLE "public"."b2c_song_creations" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."b2c_song_creations_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."b2c_song_jobs" (
    "id" "uuid" DEFAULT "extensions"."uuid_generate_v4"() NOT NULL,
    "order_id" "uuid" NOT NULL,
    "lyrics_id" "uuid" NOT NULL,
    "piapi_job_id" "text",
    "status" "text" DEFAULT 'pending'::"text" NOT NULL,
    "suno_prompt" "text",
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"(),
    "error_message" "text",
    "metadata" "jsonb"
);


ALTER TABLE "public"."b2c_song_jobs" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."b2c_songs" (
    "id" "uuid" DEFAULT "extensions"."uuid_generate_v4"() NOT NULL,
    "order_id" "uuid" NOT NULL,
    "lyrics_id" "uuid",
    "storage_path" "text",
    "format" "text",
    "duration" integer,
    "created_at" timestamp with time zone DEFAULT "now"(),
    "status" "public"."b2c_song_status" DEFAULT 'pending'::"public"."b2c_song_status",
    "revision_number" integer DEFAULT 1
);


ALTER TABLE "public"."b2c_songs" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."b2c_whatsapp_contacts" (
    "id" bigint NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "wa_id" "text" NOT NULL,
    "profile_name" "text",
    "last_message_received_at" timestamp with time zone,
    "last_message_content" "text",
    "status" "text" DEFAULT 'Prospect'::"text",
    "allow_contact" boolean DEFAULT true NOT NULL
);


ALTER TABLE "public"."b2c_whatsapp_contacts" OWNER TO "postgres";


ALTER TABLE "public"."b2c_whatsapp_contacts" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."b2c_whatsapp_contacts_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."b2c_whatsapp_messages" (
    "id" bigint NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "wa_id" "text",
    "type" "text",
    "message" "text",
    "url" "text",
    "timestamp" "text",
    "wa_number_id" "text",
    "direction" "text",
    "msg_id" "text"
);


ALTER TABLE "public"."b2c_whatsapp_messages" OWNER TO "postgres";


ALTER TABLE "public"."b2c_whatsapp_messages" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."b2c_whatsapp_messages_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."birthday_information_gathering" (
    "id" bigint NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "birthday_employee" bigint,
    "respondent_employee" bigint,
    "status" "text",
    "information_summary" "text",
    "year" integer,
    "last_received_coversation" timestamp with time zone,
    "last_sent_conversation_time" timestamp with time zone,
    "reminder_count" bigint,
    "wa_id" "text"
);


ALTER TABLE "public"."birthday_information_gathering" OWNER TO "postgres";


ALTER TABLE "public"."birthday_information_gathering" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."birthday_information_gathering_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



ALTER TABLE "public"."employees" ALTER COLUMN "employee_id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."employees_employee_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."lyrics_creations" (
    "id" bigint NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "consumer_id" bigint,
    "lyrics_creation_id" "text",
    "lyrics_status" "text",
    "lyrics" "text"
);


ALTER TABLE "public"."lyrics_creations" OWNER TO "postgres";


ALTER TABLE "public"."lyrics_creations" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."lyrics_creations_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."messages" (
    "id" bigint NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "birthday_employee_id" bigint,
    "respondent_employee_id" bigint,
    "direction" "text",
    "message" "text"
);


ALTER TABLE "public"."messages" OWNER TO "postgres";


ALTER TABLE "public"."messages" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."messages_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."razorpay_payments_register" (
    "id" bigint NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "payment_number" "text",
    "payment_email" "text",
    "value" double precision,
    "is_used" boolean DEFAULT false,
    "transaction_id" "text"
);


ALTER TABLE "public"."razorpay_payments_register" OWNER TO "postgres";


ALTER TABLE "public"."razorpay_payments_register" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."razorpay_payments_register_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."users" (
    "user_id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "company_name" "text",
    "email_address" "text",
    "profile_pic" "text",
    "designation" "text",
    "department" "text",
    "company_size" "text",
    "phone_number" "text",
    "approved" boolean DEFAULT false,
    "user_name" "text",
    "company_id" bigint NOT NULL
);


ALTER TABLE "public"."users" OWNER TO "postgres";


COMMENT ON TABLE "public"."users" IS 'This holds the additional information of all the users';



ALTER TABLE "public"."users" ALTER COLUMN "company_id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."users_company_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



ALTER TABLE ONLY "public"."b2c_chat_messages"
    ADD CONSTRAINT "b2c_chat_messages_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."b2c_chat_sessions"
    ADD CONSTRAINT "b2c_chat_sessions_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."b2c_customers"
    ADD CONSTRAINT "b2c_customers_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."b2c_error_logs"
    ADD CONSTRAINT "b2c_error_logs_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."b2c_image_creations_duplicate"
    ADD CONSTRAINT "b2c_image_creations_duplicate_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."b2c_interactions_customers"
    ADD CONSTRAINT "b2c_interactions_customers_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."b2c_lyrics"
    ADD CONSTRAINT "b2c_lyrics_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."b2c_order_details"
    ADD CONSTRAINT "b2c_order_details_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."b2c_orders"
    ADD CONSTRAINT "b2c_orders_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."b2c_payments"
    ADD CONSTRAINT "b2c_payments_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."b2c_profiles"
    ADD CONSTRAINT "b2c_profiles_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."b2c_recipient_info"
    ADD CONSTRAINT "b2c_recipient_info_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."b2c_revisions"
    ADD CONSTRAINT "b2c_revisions_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."b2c_samples"
    ADD CONSTRAINT "b2c_samples_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."b2c_song_creations"
    ADD CONSTRAINT "b2c_song_creations_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."b2c_song_jobs"
    ADD CONSTRAINT "b2c_song_jobs_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."b2c_songs"
    ADD CONSTRAINT "b2c_songs_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."b2c_whatsapp_contacts"
    ADD CONSTRAINT "b2c_whatsapp_contacts_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."b2c_whatsapp_contacts"
    ADD CONSTRAINT "b2c_whatsapp_contacts_wa_id_key" UNIQUE ("wa_id");



ALTER TABLE ONLY "public"."b2c_whatsapp_messages"
    ADD CONSTRAINT "b2c_whatsapp_messages_msg_id_key" UNIQUE ("msg_id");



ALTER TABLE ONLY "public"."b2c_whatsapp_messages"
    ADD CONSTRAINT "b2c_whatsapp_messages_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."birthday_information_gathering"
    ADD CONSTRAINT "birthday_information_gathering_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."employees"
    ADD CONSTRAINT "employees_company_employee_id_key" UNIQUE ("company_employee_id");



ALTER TABLE ONLY "public"."employees"
    ADD CONSTRAINT "employees_pkey" PRIMARY KEY ("employee_id");



ALTER TABLE ONLY "public"."lyrics_creations"
    ADD CONSTRAINT "lyrics_creations_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."messages"
    ADD CONSTRAINT "messages_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."razorpay_payments_register"
    ADD CONSTRAINT "razorpay_payments_register_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."b2c_interactions_customers"
    ADD CONSTRAINT "unique_wa_id" UNIQUE ("wa_id");



ALTER TABLE ONLY "public"."users"
    ADD CONSTRAINT "users_company_id_key" UNIQUE ("company_id");



ALTER TABLE ONLY "public"."users"
    ADD CONSTRAINT "users_pkey" PRIMARY KEY ("user_id");



CREATE UNIQUE INDEX "b2c_profiles_id_unique" ON "public"."b2c_profiles" USING "btree" ("id");



CREATE INDEX "idx_b2c_order_details_order_id" ON "public"."b2c_order_details" USING "btree" ("order_id");



CREATE INDEX "idx_b2c_orders_user_id" ON "public"."b2c_orders" USING "btree" ("user_id");



CREATE OR REPLACE TRIGGER "b2c_payments_to_b2c_orders" AFTER INSERT ON "public"."b2c_payments" FOR EACH ROW EXECUTE FUNCTION "public"."update_b2c_orders_status"();



CREATE OR REPLACE TRIGGER "b2c_update_chat_sessions_modtime" BEFORE UPDATE ON "public"."b2c_chat_sessions" FOR EACH ROW EXECUTE FUNCTION "public"."b2c_update_modified_column"();



CREATE OR REPLACE TRIGGER "b2c_update_orders_modtime" BEFORE UPDATE ON "public"."b2c_orders" FOR EACH ROW EXECUTE FUNCTION "public"."b2c_update_modified_column"();



CREATE OR REPLACE TRIGGER "b2c_update_profiles_modtime" BEFORE UPDATE ON "public"."b2c_profiles" FOR EACH ROW EXECUTE FUNCTION "public"."b2c_update_modified_column"();



CREATE OR REPLACE TRIGGER "b2c_update_recipient_info_modtime" BEFORE UPDATE ON "public"."b2c_recipient_info" FOR EACH ROW EXECUTE FUNCTION "public"."b2c_update_modified_column"();



CREATE OR REPLACE TRIGGER "b2c_update_song_jobs_modtime" BEFORE UPDATE ON "public"."b2c_song_jobs" FOR EACH ROW EXECUTE FUNCTION "public"."b2c_update_modified_column"();



CREATE OR REPLACE TRIGGER "set_is_recent" BEFORE INSERT OR UPDATE OF "last_message_received_time" ON "public"."b2c_interactions_customers" FOR EACH ROW EXECUTE FUNCTION "public"."update_is_recent"();



CREATE OR REPLACE TRIGGER "trigger_update_birthday_fields" BEFORE INSERT OR UPDATE OF "dob" ON "public"."employees" FOR EACH ROW EXECUTE FUNCTION "public"."update_birthday_fields"();



CREATE OR REPLACE TRIGGER "trigger_update_birthdays" BEFORE INSERT OR UPDATE OF "dob" ON "public"."employees" FOR EACH ROW EXECUTE FUNCTION "public"."trigger_update_employee_birthdays"();



CREATE OR REPLACE TRIGGER "trigger_update_contact_last_message" AFTER INSERT ON "public"."b2c_whatsapp_messages" FOR EACH ROW EXECUTE FUNCTION "public"."update_last_message_received"();



ALTER TABLE ONLY "public"."b2c_chat_messages"
    ADD CONSTRAINT "b2c_chat_messages_session_id_fkey" FOREIGN KEY ("session_id") REFERENCES "public"."b2c_chat_sessions"("id");



ALTER TABLE ONLY "public"."b2c_chat_sessions"
    ADD CONSTRAINT "b2c_chat_sessions_order_id_fkey" FOREIGN KEY ("order_id") REFERENCES "public"."b2c_orders"("id");



ALTER TABLE ONLY "public"."b2c_chat_sessions"
    ADD CONSTRAINT "b2c_chat_sessions_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."b2c_profiles"("id");



ALTER TABLE ONLY "public"."b2c_error_logs"
    ADD CONSTRAINT "b2c_error_logs_order_id_fkey" FOREIGN KEY ("order_id") REFERENCES "public"."b2c_orders"("id");



ALTER TABLE ONLY "public"."b2c_lyrics"
    ADD CONSTRAINT "b2c_lyrics_order_id_fkey" FOREIGN KEY ("order_id") REFERENCES "public"."b2c_orders"("id");



ALTER TABLE ONLY "public"."b2c_order_details"
    ADD CONSTRAINT "b2c_order_details_order_id_fkey" FOREIGN KEY ("order_id") REFERENCES "public"."b2c_orders"("id");



ALTER TABLE ONLY "public"."b2c_orders"
    ADD CONSTRAINT "b2c_orders_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."b2c_profiles"("id");



ALTER TABLE ONLY "public"."b2c_payments"
    ADD CONSTRAINT "b2c_payments_order_id_fkey" FOREIGN KEY ("order_id") REFERENCES "public"."b2c_orders"("id");



ALTER TABLE ONLY "public"."b2c_profiles"
    ADD CONSTRAINT "b2c_profiles_id_fkey" FOREIGN KEY ("id") REFERENCES "auth"."users"("id");



ALTER TABLE ONLY "public"."b2c_recipient_info"
    ADD CONSTRAINT "b2c_recipient_info_order_id_fkey" FOREIGN KEY ("order_id") REFERENCES "public"."b2c_orders"("id");



ALTER TABLE ONLY "public"."b2c_revisions"
    ADD CONSTRAINT "b2c_revisions_order_id_fkey" FOREIGN KEY ("order_id") REFERENCES "public"."b2c_orders"("id");



ALTER TABLE ONLY "public"."b2c_revisions"
    ADD CONSTRAINT "b2c_revisions_requested_by_fkey" FOREIGN KEY ("requested_by") REFERENCES "public"."b2c_profiles"("id");



ALTER TABLE ONLY "public"."b2c_song_jobs"
    ADD CONSTRAINT "b2c_song_jobs_lyrics_id_fkey" FOREIGN KEY ("lyrics_id") REFERENCES "public"."b2c_lyrics"("id");



ALTER TABLE ONLY "public"."b2c_song_jobs"
    ADD CONSTRAINT "b2c_song_jobs_order_id_fkey" FOREIGN KEY ("order_id") REFERENCES "public"."b2c_orders"("id");



ALTER TABLE ONLY "public"."b2c_songs"
    ADD CONSTRAINT "b2c_songs_lyrics_id_fkey" FOREIGN KEY ("lyrics_id") REFERENCES "public"."b2c_lyrics"("id");



ALTER TABLE ONLY "public"."b2c_songs"
    ADD CONSTRAINT "b2c_songs_order_id_fkey" FOREIGN KEY ("order_id") REFERENCES "public"."b2c_orders"("id");



ALTER TABLE ONLY "public"."birthday_information_gathering"
    ADD CONSTRAINT "birthday_information_gathering_birthday_employee_fkey" FOREIGN KEY ("birthday_employee") REFERENCES "public"."employees"("employee_id");



ALTER TABLE ONLY "public"."birthday_information_gathering"
    ADD CONSTRAINT "birthday_information_gathering_respondent_employee_fkey" FOREIGN KEY ("respondent_employee") REFERENCES "public"."employees"("employee_id");



ALTER TABLE ONLY "public"."employees"
    ADD CONSTRAINT "employees_company_id_fkey" FOREIGN KEY ("company_id") REFERENCES "public"."users"("company_id") ON UPDATE CASCADE;



ALTER TABLE ONLY "public"."lyrics_creations"
    ADD CONSTRAINT "lyrics_creations_consumer_id_fkey" FOREIGN KEY ("consumer_id") REFERENCES "public"."b2c_customers"("id") ON UPDATE CASCADE ON DELETE SET NULL;



ALTER TABLE ONLY "public"."messages"
    ADD CONSTRAINT "messages_respondent_employee_id_fkey" FOREIGN KEY ("respondent_employee_id") REFERENCES "public"."employees"("employee_id");



ALTER TABLE ONLY "public"."messages"
    ADD CONSTRAINT "messages_respondent_employee_id_fkey1" FOREIGN KEY ("respondent_employee_id") REFERENCES "public"."employees"("employee_id");



ALTER TABLE ONLY "public"."users"
    ADD CONSTRAINT "users_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "auth"."users"("id");



CREATE POLICY "Allow Users to create Order Details" ON "public"."b2c_order_details" FOR INSERT TO "authenticated" WITH CHECK (("auth"."uid"() = "id"));



CREATE POLICY "Allow authenticated insert" ON "public"."b2c_error_logs" FOR INSERT TO "authenticated" WITH CHECK (true);



CREATE POLICY "Allow delete with matching order_id" ON "public"."b2c_recipient_info" FOR DELETE USING (true);



CREATE POLICY "Allow insert for anyone" ON "public"."b2c_recipient_info" FOR INSERT WITH CHECK (true);



CREATE POLICY "Allow inserts based on order ownership" ON "public"."b2c_order_details" FOR INSERT TO "authenticated" WITH CHECK (("order_id" IN ( SELECT "b2c_orders"."id"
   FROM "public"."b2c_orders"
  WHERE ("b2c_orders"."user_id" = "auth"."uid"()))));



CREATE POLICY "Allow public to create orders" ON "public"."b2c_orders" FOR INSERT TO "authenticated", "anon" WITH CHECK (true);



CREATE POLICY "Allow public to create profiles" ON "public"."b2c_profiles" FOR INSERT TO "authenticated", "anon" WITH CHECK (true);



CREATE POLICY "Allow read access with order_id" ON "public"."b2c_recipient_info" FOR SELECT USING (true);



CREATE POLICY "Allow update with matching order_id" ON "public"."b2c_recipient_info" FOR UPDATE USING (true);



CREATE POLICY "Allow updates for owned orders" ON "public"."b2c_order_details" FOR UPDATE TO "authenticated" USING (("order_id" IN ( SELECT "b2c_orders"."id"
   FROM "public"."b2c_orders"
  WHERE ("b2c_orders"."user_id" = "auth"."uid"()))));



CREATE POLICY "Allow viewing records for owned orders" ON "public"."b2c_order_details" FOR SELECT TO "authenticated" USING (("order_id" IN ( SELECT "b2c_orders"."id"
   FROM "public"."b2c_orders"
  WHERE ("b2c_orders"."user_id" = "auth"."uid"()))));



CREATE POLICY "Anon can view lyrics" ON "public"."b2c_lyrics" FOR SELECT TO "anon" USING (true);



CREATE POLICY "Anyone can view orders by ID" ON "public"."b2c_orders" FOR SELECT USING (true);



CREATE POLICY "Enable read access to b2c_orders" ON "public"."b2c_orders" FOR SELECT USING (("auth"."uid"() = "user_id"));



CREATE POLICY "Enable users to insert their own payments" ON "public"."b2c_payments" FOR SELECT TO "authenticated" USING (("auth"."uid"() IN ( SELECT "b2c_orders"."user_id"
   FROM "public"."b2c_orders"
  WHERE ("b2c_orders"."id" = "b2c_payments"."order_id"))));



CREATE POLICY "Service can access all order details" ON "public"."b2c_order_details" FOR SELECT USING ((("auth"."role"() = 'service_role'::"text") OR ("auth"."role"() = 'anon'::"text")));



CREATE POLICY "Service can access all recipient info" ON "public"."b2c_recipient_info" FOR SELECT USING ((("auth"."role"() = 'service_role'::"text") OR ("auth"."role"() = 'anon'::"text")));



CREATE POLICY "Service can insert all lyrics" ON "public"."b2c_lyrics" FOR INSERT WITH CHECK ((("auth"."role"() = 'service_role'::"text") OR ("auth"."role"() = 'anon'::"text")));



CREATE POLICY "Service can insert lyrics" ON "public"."b2c_lyrics" FOR INSERT TO "service_role" WITH CHECK (true);



CREATE POLICY "Service can update all orders" ON "public"."b2c_orders" FOR UPDATE USING ((("auth"."role"() = 'service_role'::"text") OR ("auth"."role"() = 'anon'::"text")));



CREATE POLICY "Service can update any order" ON "public"."b2c_orders" FOR UPDATE TO "service_role" USING (true) WITH CHECK (true);



CREATE POLICY "Service can update lyrics" ON "public"."b2c_lyrics" FOR UPDATE TO "service_role" USING (true) WITH CHECK (true);



CREATE POLICY "Service can view all lyrics" ON "public"."b2c_lyrics" FOR SELECT TO "service_role" USING (true);



CREATE POLICY "Service can view all orders" ON "public"."b2c_orders" FOR SELECT TO "service_role" USING (true);



CREATE POLICY "Service role full access to orders" ON "public"."b2c_orders" TO "service_role" USING (true);



CREATE POLICY "Service role full access to profiles" ON "public"."b2c_profiles" TO "service_role" USING (true);



CREATE POLICY "Users can create orders" ON "public"."b2c_orders" FOR INSERT WITH CHECK (("auth"."uid"() = "user_id"));



CREATE POLICY "Users can create their own profile" ON "public"."b2c_profiles" FOR INSERT TO "authenticated" WITH CHECK (("auth"."uid"() = "id"));



CREATE POLICY "Users can insert lyrics for their orders" ON "public"."b2c_lyrics" FOR INSERT WITH CHECK ((EXISTS ( SELECT 1
   FROM "public"."b2c_orders"
  WHERE (("b2c_orders"."id" = "b2c_lyrics"."order_id") AND ("b2c_orders"."user_id" = "auth"."uid"())))));



CREATE POLICY "Users can insert recipient info for their orders" ON "public"."b2c_recipient_info" FOR INSERT WITH CHECK ((EXISTS ( SELECT 1
   FROM "public"."b2c_orders"
  WHERE (("b2c_orders"."id" = "b2c_recipient_info"."order_id") AND ("b2c_orders"."user_id" = "auth"."uid"())))));



CREATE POLICY "Users can insert revisions for their orders" ON "public"."b2c_revisions" FOR INSERT WITH CHECK ((( SELECT (EXISTS ( SELECT 1
           FROM "public"."b2c_orders"
          WHERE (("b2c_orders"."id" = "b2c_revisions"."order_id") AND ("b2c_orders"."user_id" = "auth"."uid"())))) AS "exists") OR ("requested_by" = "auth"."uid"())));



CREATE POLICY "Users can insert their order details" ON "public"."b2c_order_details" FOR INSERT WITH CHECK ((EXISTS ( SELECT 1
   FROM "public"."b2c_orders"
  WHERE (("b2c_orders"."id" = "b2c_order_details"."order_id") AND ("b2c_orders"."user_id" = "auth"."uid"())))));



CREATE POLICY "Users can insert their own order details" ON "public"."b2c_order_details" FOR INSERT WITH CHECK (("auth"."uid"() IN ( SELECT "b2c_orders"."user_id"
   FROM "public"."b2c_orders"
  WHERE ("b2c_orders"."id" = "b2c_order_details"."order_id"))));



CREATE POLICY "Users can insert their own orders" ON "public"."b2c_orders" FOR INSERT WITH CHECK (("auth"."uid"() = "user_id"));



CREATE POLICY "Users can insert their own payments" ON "public"."b2c_payments" FOR INSERT WITH CHECK (("auth"."uid"() IN ( SELECT "b2c_orders"."user_id"
   FROM "public"."b2c_orders"
  WHERE ("b2c_orders"."id" = "b2c_payments"."order_id"))));



CREATE POLICY "Users can update lyrics for their orders" ON "public"."b2c_lyrics" FOR UPDATE USING ((EXISTS ( SELECT 1
   FROM "public"."b2c_orders"
  WHERE (("b2c_orders"."id" = "b2c_lyrics"."order_id") AND ("b2c_orders"."user_id" = "auth"."uid"())))));



CREATE POLICY "Users can update own profile" ON "public"."b2c_profiles" FOR UPDATE TO "authenticated" USING (("auth"."uid"() = "id"));



CREATE POLICY "Users can update recipient info for their orders" ON "public"."b2c_recipient_info" FOR UPDATE USING ((EXISTS ( SELECT 1
   FROM "public"."b2c_orders"
  WHERE (("b2c_orders"."id" = "b2c_recipient_info"."order_id") AND ("b2c_orders"."user_id" = "auth"."uid"())))));



CREATE POLICY "Users can update their order details" ON "public"."b2c_order_details" FOR UPDATE USING ((EXISTS ( SELECT 1
   FROM "public"."b2c_orders"
  WHERE (("b2c_orders"."id" = "b2c_order_details"."order_id") AND ("b2c_orders"."user_id" = "auth"."uid"())))));



CREATE POLICY "Users can update their own orders" ON "public"."b2c_orders" FOR UPDATE USING (("auth"."uid"() = "user_id"));



CREATE POLICY "Users can update their own profile" ON "public"."b2c_profiles" FOR UPDATE USING (("auth"."uid"() = "id"));



CREATE POLICY "Users can view lyrics for their orders" ON "public"."b2c_lyrics" FOR SELECT USING ((EXISTS ( SELECT 1
   FROM "public"."b2c_orders"
  WHERE (("b2c_orders"."id" = "b2c_lyrics"."order_id") AND ("b2c_orders"."user_id" = "auth"."uid"())))));



CREATE POLICY "Users can view messages for their chat sessions" ON "public"."b2c_chat_messages" FOR SELECT USING ((EXISTS ( SELECT 1
   FROM "public"."b2c_chat_sessions"
  WHERE (("b2c_chat_sessions"."id" = "b2c_chat_messages"."session_id") AND ("b2c_chat_sessions"."user_id" = "auth"."uid"())))));



CREATE POLICY "Users can view order details for their orders" ON "public"."b2c_order_details" FOR SELECT TO "authenticated" USING ((EXISTS ( SELECT 1
   FROM "public"."b2c_orders"
  WHERE (("b2c_orders"."id" = "b2c_order_details"."order_id") AND ("b2c_orders"."user_id" = "auth"."uid"())))));



CREATE POLICY "Users can view own orders" ON "public"."b2c_orders" FOR SELECT TO "authenticated" USING ((("auth"."uid"() = "user_id") OR ("user_id" IS NULL)));



CREATE POLICY "Users can view own profile" ON "public"."b2c_profiles" FOR SELECT TO "authenticated" USING (("auth"."uid"() = "id"));



CREATE POLICY "Users can view recipient info for their orders" ON "public"."b2c_recipient_info" FOR SELECT USING ((EXISTS ( SELECT 1
   FROM "public"."b2c_orders"
  WHERE (("b2c_orders"."id" = "b2c_recipient_info"."order_id") AND ("b2c_orders"."user_id" = "auth"."uid"())))));



CREATE POLICY "Users can view recipient info for their orders using order id" ON "public"."b2c_recipient_info" FOR SELECT USING ((EXISTS ( SELECT 1
   FROM "public"."b2c_orders"
  WHERE (("b2c_orders"."id" = "b2c_recipient_info"."order_id") AND ("b2c_orders"."user_id" = "auth"."uid"())))));



CREATE POLICY "Users can view revisions for their orders" ON "public"."b2c_revisions" FOR SELECT USING ((EXISTS ( SELECT 1
   FROM "public"."b2c_orders"
  WHERE (("b2c_orders"."id" = "b2c_revisions"."order_id") AND ("b2c_orders"."user_id" = "auth"."uid"())))));



CREATE POLICY "Users can view song jobs for their orders" ON "public"."b2c_song_jobs" FOR SELECT USING ((EXISTS ( SELECT 1
   FROM "public"."b2c_orders"
  WHERE (("b2c_orders"."id" = "b2c_song_jobs"."order_id") AND ("b2c_orders"."user_id" = "auth"."uid"())))));



CREATE POLICY "Users can view songs for their orders" ON "public"."b2c_songs" FOR SELECT USING ((EXISTS ( SELECT 1
   FROM "public"."b2c_orders"
  WHERE (("b2c_orders"."id" = "b2c_songs"."order_id") AND ("b2c_orders"."user_id" = "auth"."uid"())))));



CREATE POLICY "Users can view their chat sessions" ON "public"."b2c_chat_sessions" FOR SELECT USING (("auth"."uid"() = "user_id"));



CREATE POLICY "Users can view their order details" ON "public"."b2c_order_details" FOR SELECT USING ((EXISTS ( SELECT 1
   FROM "public"."b2c_orders"
  WHERE (("b2c_orders"."id" = "b2c_order_details"."order_id") AND ("b2c_orders"."user_id" = "auth"."uid"())))));



CREATE POLICY "Users can view their own lyrics" ON "public"."b2c_lyrics" FOR SELECT TO "authenticated" USING ((EXISTS ( SELECT 1
   FROM "public"."b2c_orders"
  WHERE (("b2c_orders"."id" = "b2c_lyrics"."order_id") AND ("b2c_orders"."user_id" = "auth"."uid"())))));



CREATE POLICY "Users can view their own orders" ON "public"."b2c_orders" FOR SELECT USING (("auth"."uid"() = "user_id"));



CREATE POLICY "Users can view their own profile" ON "public"."b2c_profiles" FOR SELECT USING (("auth"."uid"() = "id"));



CREATE POLICY "Users can view their payments" ON "public"."b2c_payments" FOR SELECT USING ((EXISTS ( SELECT 1
   FROM "public"."b2c_orders"
  WHERE (("b2c_orders"."id" = "b2c_payments"."order_id") AND ("b2c_orders"."user_id" = "auth"."uid"())))));



ALTER TABLE "public"."b2c_chat_messages" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."b2c_chat_sessions" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."b2c_error_logs" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."b2c_lyrics" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."b2c_order_details" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."b2c_orders" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."b2c_payments" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."b2c_profiles" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."b2c_recipient_info" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."b2c_revisions" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."b2c_song_jobs" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."b2c_songs" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."razorpay_payments_register" ENABLE ROW LEVEL SECURITY;




ALTER PUBLICATION "supabase_realtime" OWNER TO "postgres";






ALTER PUBLICATION "supabase_realtime" ADD TABLE ONLY "public"."b2c_whatsapp_contacts";



ALTER PUBLICATION "supabase_realtime" ADD TABLE ONLY "public"."b2c_whatsapp_messages";






GRANT USAGE ON SCHEMA "public" TO "postgres";
GRANT USAGE ON SCHEMA "public" TO "anon";
GRANT USAGE ON SCHEMA "public" TO "authenticated";
GRANT USAGE ON SCHEMA "public" TO "service_role";









































































































































































































GRANT ALL ON FUNCTION "public"."b2c_update_modified_column"() TO "anon";
GRANT ALL ON FUNCTION "public"."b2c_update_modified_column"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."b2c_update_modified_column"() TO "service_role";



GRANT ALL ON FUNCTION "public"."daily_update_birthdays"() TO "anon";
GRANT ALL ON FUNCTION "public"."daily_update_birthdays"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."daily_update_birthdays"() TO "service_role";



GRANT ALL ON FUNCTION "public"."get_connect_worthy_contacts"() TO "anon";
GRANT ALL ON FUNCTION "public"."get_connect_worthy_contacts"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."get_connect_worthy_contacts"() TO "service_role";



GRANT ALL ON FUNCTION "public"."get_employee_and_birthday_info"("input_phone" "text") TO "anon";
GRANT ALL ON FUNCTION "public"."get_employee_and_birthday_info"("input_phone" "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."get_employee_and_birthday_info"("input_phone" "text") TO "service_role";



GRANT ALL ON TABLE "public"."employees" TO "anon";
GRANT ALL ON TABLE "public"."employees" TO "authenticated";
GRANT ALL ON TABLE "public"."employees" TO "service_role";



GRANT ALL ON FUNCTION "public"."get_related_employees"("p_employee_id" integer) TO "anon";
GRANT ALL ON FUNCTION "public"."get_related_employees"("p_employee_id" integer) TO "authenticated";
GRANT ALL ON FUNCTION "public"."get_related_employees"("p_employee_id" integer) TO "service_role";



GRANT ALL ON FUNCTION "public"."get_total_employees"("company_id_input" integer) TO "anon";
GRANT ALL ON FUNCTION "public"."get_total_employees"("company_id_input" integer) TO "authenticated";
GRANT ALL ON FUNCTION "public"."get_total_employees"("company_id_input" integer) TO "service_role";



GRANT ALL ON FUNCTION "public"."handle_new_user"() TO "anon";
GRANT ALL ON FUNCTION "public"."handle_new_user"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."handle_new_user"() TO "service_role";



GRANT ALL ON FUNCTION "public"."trigger_update_employee_birthdays"() TO "anon";
GRANT ALL ON FUNCTION "public"."trigger_update_employee_birthdays"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."trigger_update_employee_birthdays"() TO "service_role";



GRANT ALL ON FUNCTION "public"."update_b2c_orders_status"() TO "anon";
GRANT ALL ON FUNCTION "public"."update_b2c_orders_status"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."update_b2c_orders_status"() TO "service_role";



GRANT ALL ON FUNCTION "public"."update_b2c_profiles_uid"() TO "anon";
GRANT ALL ON FUNCTION "public"."update_b2c_profiles_uid"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."update_b2c_profiles_uid"() TO "service_role";



GRANT ALL ON FUNCTION "public"."update_birthday_fields"() TO "anon";
GRANT ALL ON FUNCTION "public"."update_birthday_fields"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."update_birthday_fields"() TO "service_role";



GRANT ALL ON FUNCTION "public"."update_employee_birthdays"() TO "anon";
GRANT ALL ON FUNCTION "public"."update_employee_birthdays"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."update_employee_birthdays"() TO "service_role";



GRANT ALL ON FUNCTION "public"."update_is_recent"() TO "anon";
GRANT ALL ON FUNCTION "public"."update_is_recent"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."update_is_recent"() TO "service_role";



GRANT ALL ON FUNCTION "public"."update_is_recent_status"() TO "anon";
GRANT ALL ON FUNCTION "public"."update_is_recent_status"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."update_is_recent_status"() TO "service_role";



GRANT ALL ON FUNCTION "public"."update_last_message_received"() TO "anon";
GRANT ALL ON FUNCTION "public"."update_last_message_received"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."update_last_message_received"() TO "service_role";



GRANT ALL ON FUNCTION "public"."upsert_order_details"("p_order_id" "uuid", "p_recipient_name" "text", "p_relationship" "text", "p_occasion" "text", "p_language" "text", "p_mood" "text", "p_vocals" "text", "p_additional_info" "text") TO "anon";
GRANT ALL ON FUNCTION "public"."upsert_order_details"("p_order_id" "uuid", "p_recipient_name" "text", "p_relationship" "text", "p_occasion" "text", "p_language" "text", "p_mood" "text", "p_vocals" "text", "p_additional_info" "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."upsert_order_details"("p_order_id" "uuid", "p_recipient_name" "text", "p_relationship" "text", "p_occasion" "text", "p_language" "text", "p_mood" "text", "p_vocals" "text", "p_additional_info" "text") TO "service_role";
























GRANT ALL ON TABLE "public"."b2c_chat_messages" TO "anon";
GRANT ALL ON TABLE "public"."b2c_chat_messages" TO "authenticated";
GRANT ALL ON TABLE "public"."b2c_chat_messages" TO "service_role";



GRANT ALL ON TABLE "public"."b2c_chat_sessions" TO "anon";
GRANT ALL ON TABLE "public"."b2c_chat_sessions" TO "authenticated";
GRANT ALL ON TABLE "public"."b2c_chat_sessions" TO "service_role";



GRANT ALL ON TABLE "public"."b2c_customers" TO "anon";
GRANT ALL ON TABLE "public"."b2c_customers" TO "authenticated";
GRANT ALL ON TABLE "public"."b2c_customers" TO "service_role";



GRANT ALL ON SEQUENCE "public"."b2c_customers_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."b2c_customers_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."b2c_customers_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."b2c_error_logs" TO "anon";
GRANT ALL ON TABLE "public"."b2c_error_logs" TO "authenticated";
GRANT ALL ON TABLE "public"."b2c_error_logs" TO "service_role";



GRANT ALL ON TABLE "public"."b2c_image_creations_duplicate" TO "anon";
GRANT ALL ON TABLE "public"."b2c_image_creations_duplicate" TO "authenticated";
GRANT ALL ON TABLE "public"."b2c_image_creations_duplicate" TO "service_role";



GRANT ALL ON SEQUENCE "public"."b2c_image_creations_duplicate_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."b2c_image_creations_duplicate_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."b2c_image_creations_duplicate_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."b2c_interactions_customers" TO "anon";
GRANT ALL ON TABLE "public"."b2c_interactions_customers" TO "authenticated";
GRANT ALL ON TABLE "public"."b2c_interactions_customers" TO "service_role";



GRANT ALL ON SEQUENCE "public"."b2c_interactions_customers_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."b2c_interactions_customers_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."b2c_interactions_customers_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."b2c_lyrics" TO "anon";
GRANT ALL ON TABLE "public"."b2c_lyrics" TO "authenticated";
GRANT ALL ON TABLE "public"."b2c_lyrics" TO "service_role";



GRANT ALL ON TABLE "public"."b2c_order_details" TO "anon";
GRANT ALL ON TABLE "public"."b2c_order_details" TO "authenticated";
GRANT ALL ON TABLE "public"."b2c_order_details" TO "service_role";



GRANT ALL ON TABLE "public"."b2c_orders" TO "anon";
GRANT ALL ON TABLE "public"."b2c_orders" TO "authenticated";
GRANT ALL ON TABLE "public"."b2c_orders" TO "service_role";



GRANT ALL ON TABLE "public"."b2c_payments" TO "anon";
GRANT ALL ON TABLE "public"."b2c_payments" TO "authenticated";
GRANT ALL ON TABLE "public"."b2c_payments" TO "service_role";



GRANT ALL ON TABLE "public"."b2c_profiles" TO "anon";
GRANT ALL ON TABLE "public"."b2c_profiles" TO "authenticated";
GRANT ALL ON TABLE "public"."b2c_profiles" TO "service_role";



GRANT ALL ON TABLE "public"."b2c_recipient_info" TO "anon";
GRANT ALL ON TABLE "public"."b2c_recipient_info" TO "authenticated";
GRANT ALL ON TABLE "public"."b2c_recipient_info" TO "service_role";



GRANT ALL ON TABLE "public"."b2c_revisions" TO "anon";
GRANT ALL ON TABLE "public"."b2c_revisions" TO "authenticated";
GRANT ALL ON TABLE "public"."b2c_revisions" TO "service_role";



GRANT ALL ON TABLE "public"."b2c_samples" TO "anon";
GRANT ALL ON TABLE "public"."b2c_samples" TO "authenticated";
GRANT ALL ON TABLE "public"."b2c_samples" TO "service_role";



GRANT ALL ON SEQUENCE "public"."b2c_samples_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."b2c_samples_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."b2c_samples_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."b2c_song_creations" TO "anon";
GRANT ALL ON TABLE "public"."b2c_song_creations" TO "authenticated";
GRANT ALL ON TABLE "public"."b2c_song_creations" TO "service_role";



GRANT ALL ON SEQUENCE "public"."b2c_song_creations_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."b2c_song_creations_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."b2c_song_creations_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."b2c_song_jobs" TO "anon";
GRANT ALL ON TABLE "public"."b2c_song_jobs" TO "authenticated";
GRANT ALL ON TABLE "public"."b2c_song_jobs" TO "service_role";



GRANT ALL ON TABLE "public"."b2c_songs" TO "anon";
GRANT ALL ON TABLE "public"."b2c_songs" TO "authenticated";
GRANT ALL ON TABLE "public"."b2c_songs" TO "service_role";



GRANT ALL ON TABLE "public"."b2c_whatsapp_contacts" TO "anon";
GRANT ALL ON TABLE "public"."b2c_whatsapp_contacts" TO "authenticated";
GRANT ALL ON TABLE "public"."b2c_whatsapp_contacts" TO "service_role";



GRANT ALL ON SEQUENCE "public"."b2c_whatsapp_contacts_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."b2c_whatsapp_contacts_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."b2c_whatsapp_contacts_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."b2c_whatsapp_messages" TO "anon";
GRANT ALL ON TABLE "public"."b2c_whatsapp_messages" TO "authenticated";
GRANT ALL ON TABLE "public"."b2c_whatsapp_messages" TO "service_role";



GRANT ALL ON SEQUENCE "public"."b2c_whatsapp_messages_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."b2c_whatsapp_messages_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."b2c_whatsapp_messages_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."birthday_information_gathering" TO "anon";
GRANT ALL ON TABLE "public"."birthday_information_gathering" TO "authenticated";
GRANT ALL ON TABLE "public"."birthday_information_gathering" TO "service_role";



GRANT ALL ON SEQUENCE "public"."birthday_information_gathering_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."birthday_information_gathering_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."birthday_information_gathering_id_seq" TO "service_role";



GRANT ALL ON SEQUENCE "public"."employees_employee_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."employees_employee_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."employees_employee_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."lyrics_creations" TO "anon";
GRANT ALL ON TABLE "public"."lyrics_creations" TO "authenticated";
GRANT ALL ON TABLE "public"."lyrics_creations" TO "service_role";



GRANT ALL ON SEQUENCE "public"."lyrics_creations_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."lyrics_creations_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."lyrics_creations_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."messages" TO "anon";
GRANT ALL ON TABLE "public"."messages" TO "authenticated";
GRANT ALL ON TABLE "public"."messages" TO "service_role";



GRANT ALL ON SEQUENCE "public"."messages_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."messages_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."messages_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."razorpay_payments_register" TO "anon";
GRANT ALL ON TABLE "public"."razorpay_payments_register" TO "authenticated";
GRANT ALL ON TABLE "public"."razorpay_payments_register" TO "service_role";



GRANT ALL ON SEQUENCE "public"."razorpay_payments_register_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."razorpay_payments_register_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."razorpay_payments_register_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."users" TO "anon";
GRANT ALL ON TABLE "public"."users" TO "authenticated";
GRANT ALL ON TABLE "public"."users" TO "service_role";



GRANT ALL ON SEQUENCE "public"."users_company_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."users_company_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."users_company_id_seq" TO "service_role";



ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES  TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES  TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES  TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES  TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS  TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS  TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS  TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS  TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES  TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES  TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES  TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES  TO "service_role";






























RESET ALL;
