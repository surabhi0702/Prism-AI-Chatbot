WITH patient_convs AS (
    SELECT id, total_messages, escalated, meta_json, updated_at
    FROM conversations
    WHERE user_id = :user_id AND updated_at >= :cutoff
),
all_messages AS (
    SELECT m.role, m.content, m.confidence, m.frustration, m.citations, m.processing_ms, m.conversation_id
    FROM messages m
    JOIN conversations c ON c.id = m.conversation_id
    WHERE c.user_id = :user_id AND c.updated_at >= :cutoff
),
star_score AS (
    SELECT COALESCE(ROUND((AVG(rating)::numeric-1)/4.0*100, 1), 60) AS v
    FROM patient_feedback WHERE user_id=:user_id AND created_at>=:cutoff
),
depth_score AS (
    SELECT ROUND(LEAST(AVG(total_messages)::numeric/20.0, 1.0)*100, 1) AS v FROM patient_convs
),
return_score AS (
    SELECT ROUND(LEAST(COUNT(*)::numeric/3.0, 1.0)*100, 1) AS v FROM patient_convs
),
elab_score AS (
    SELECT COALESCE(ROUND(
        COUNT(*) FILTER (WHERE role='user' AND length(content)>100)
        ::numeric/NULLIF(COUNT(*) FILTER (WHERE role='user'), 0)*100, 1), 0) AS v
    FROM all_messages
),
ragas_scores AS (
    SELECT
        COALESCE(ROUND(AVG(rm.faithfulness)::numeric*100, 1), 60)       AS faith,
        COALESCE(ROUND(AVG(rm.answer_relevancy)::numeric*100, 1), 60)   AS relev,
        COALESCE(ROUND(AVG(rm.context_precision)::numeric*100, 1), 60)  AS prec,
        COALESCE(ROUND(AVG(rm.context_recall)::numeric*100, 1), 60)     AS recall_,
        COALESCE(ROUND(AVG(m.confidence)::numeric*100, 1), 60)          AS conf
    FROM all_messages m
    LEFT JOIN ragas_metrics rm ON rm.conversation_id=m.conversation_id
    WHERE m.role='assistant'
),
clinical_scores AS (
    SELECT
        GREATEST(0,100-(SELECT COUNT(*) FROM system_alerts WHERE level='critical' AND created_at>=:cutoff)*20) AS guardrail,
        CASE WHEN (SELECT COUNT(*) FROM patient_convs WHERE escalated)=0 THEN 85
             ELSE LEAST(100, 60 + (SELECT COUNT(*) FROM patient_convs WHERE escalated)*10) END AS esc_sc,
        GREATEST(0, 100 - (SELECT COUNT(*) FROM system_alerts WHERE title ILIKE '%emergency%' AND created_at>=:cutoff)*25) AS emg_sc,
        100 AS disclaim,
        COALESCE(ROUND(COUNT(*) FILTER (WHERE role='assistant' AND citations IS NOT NULL AND jsonb_array_length(citations::jsonb)>0)::numeric/NULLIF(COUNT(*) FILTER (WHERE role='assistant'), 0)*100, 1), 100) AS cit_rt
    FROM all_messages WHERE role='assistant'
),
flow_scores AS (
    SELECT
        75.0 AS rep_sc,
        60.0 AS slot_sc,
        75.0 AS skip_sc,
        75.0 AS intent_sc,
        75.0 AS frust_sc
),
format_scores AS (
    SELECT
        75.0 AS rot_sc,
        COALESCE(ROUND(AVG(CASE
            WHEN length(content) BETWEEN 500 AND 2000 THEN 100
            WHEN length(content) < 200 OR length(content) > 4000 THEN 25
            ELSE 65 END)::numeric, 1), 65) AS len_sc,
        COALESCE(ROUND((1-COUNT(*) FILTER (WHERE confidence<0.55)::numeric/NULLIF(COUNT(*), 0))*100, 1), 80) AS gen_sc
    FROM all_messages WHERE role='assistant'
),
velocity_scores AS (
    SELECT
        GREATEST(0,LEAST(100,ROUND(100-(AVG(processing_ms)::numeric-3000)/120.0, 1))) AS p50_sc,
        100 AS p95_sc,
        ROUND(COUNT(*) FILTER (WHERE total_messages>=8)::numeric/NULLIF(COUNT(*), 0)*100, 1) AS compl_sc
    FROM all_messages am JOIN patient_convs pc ON pc.id=am.conversation_id
    WHERE am.role='assistant' AND am.processing_ms>0
)
SELECT
    :user_id AS user_id,
    NOW() AS computed_at,
    -- Dimension Scores
    ROUND(((SELECT v FROM star_score)*0.5 + (SELECT v FROM return_score)*0.3 + (SELECT v FROM depth_score)*0.2)::numeric, 1) AS dim_engagement,
    ROUND((rs.faith*0.30 + rs.relev*0.25 + rs.prec*0.20 + rs.recall_*0.15 + rs.conf*0.10)::numeric, 1) AS dim_response,
    ROUND((cs.guardrail*0.35 + cs.esc_sc*0.25 + cs.emg_sc*0.20 + cs.disclaim*0.15 + cs.cit_rt*0.05)::numeric, 1) AS dim_clinical,
    ROUND((fs.rep_sc*0.30 + fs.slot_sc*0.25 + fs.skip_sc*0.20 + fs.intent_sc*0.15 + fs.frust_sc*0.10)::numeric, 1) AS dim_session,
    ROUND((fmt.rot_sc*0.40 + fmt.len_sc*0.35 + fmt.gen_sc*0.25)::numeric, 1) AS dim_format,
    ROUND((vs.p50_sc*0.50 + vs.p95_sc*0.30 + vs.compl_sc*0.20)::numeric, 1) AS dim_velocity,
    
    ROUND(
        (ROUND(((SELECT v FROM star_score)*0.5 + (SELECT v FROM return_score)*0.3 + (SELECT v FROM depth_score)*0.2)::numeric, 1) * 0.30 +
         ROUND((rs.faith*0.30 + rs.relev*0.25 + rs.prec*0.20 + rs.recall_*0.15 + rs.conf*0.10)::numeric, 1) * 0.25 +
         ROUND((cs.guardrail*0.35 + cs.esc_sc*0.25 + cs.emg_sc*0.20 + cs.disclaim*0.15 + cs.cit_rt*0.05)::numeric, 1) * 0.20 +
         ROUND((fs.rep_sc*0.30 + fs.slot_sc*0.25 + fs.skip_sc*0.20 + fs.intent_sc*0.15 + fs.frust_sc*0.10)::numeric, 1) * 0.15 +
         ROUND((fmt.rot_sc*0.40 + fmt.len_sc*0.35 + fmt.gen_sc*0.25)::numeric, 1) * 0.07 +
         ROUND((vs.p50_sc*0.50 + vs.p95_sc*0.30 + vs.compl_sc*0.20)::numeric, 1) * 0.03)::numeric, 
    1) AS cqs_composite,

    -- Sub-Parameter Scores
    (SELECT v FROM star_score) AS star_v,
    (SELECT v FROM elab_score) AS elab_v,
    (SELECT v FROM return_score) AS return_v,
    COALESCE(rs.faith, 60) AS faith,
    COALESCE(rs.relev, 60) AS relev,
    COALESCE(rs.conf, 60) AS conf,
    COALESCE(cs.guardrail, 100) AS guardrail,
    COALESCE(cs.emg_sc, 100) AS emg_sc,
    COALESCE(fs.rep_sc, 100) AS rep_sc,
    COALESCE(fs.skip_sc, 100) AS skip_sc,
    COALESCE(fmt.rot_sc, 75) AS rot_sc,
    COALESCE(fmt.len_sc, 75) AS len_sc,
    COALESCE(vs.p50_sc, 75) AS p50_sc,
    COALESCE(vs.p95_sc, 75) AS p95_sc
FROM (SELECT 1) d
LEFT JOIN ragas_scores rs ON TRUE
LEFT JOIN clinical_scores cs ON TRUE
LEFT JOIN flow_scores fs ON TRUE
LEFT JOIN format_scores fmt ON TRUE
LEFT JOIN velocity_scores vs ON TRUE;
