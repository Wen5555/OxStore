SET @expected_intents = 20;

SELECT
    p.id AS product_id,
    p.status AS product_status,
    COUNT(i.id) AS intent_count,
    COUNT(DISTINCT i.queue_seq) AS distinct_queue_sequences,
    MIN(i.queue_seq) AS first_queue_sequence,
    MAX(i.queue_seq) AS last_queue_sequence,
    SUM(CASE WHEN i.status <> 'QUEUING' THEN 1 ELSE 0 END) AS non_queuing_intents,
    CASE
        WHEN p.status IN ('ONLINE', 'RESTORED_ONLINE')
            AND COUNT(i.id) = @expected_intents
            AND COUNT(DISTINCT i.queue_seq) = @expected_intents
            AND MIN(i.queue_seq) = 1
            AND MAX(i.queue_seq) = @expected_intents
            AND SUM(CASE WHEN i.status <> 'QUEUING' THEN 1 ELSE 0 END) = 0
        THEN 'PASS'
        ELSE 'FAIL'
    END AS invariant_result
FROM product p
LEFT JOIN purchase_intent i ON i.product_id = p.id
WHERE p.status IN ('ONLINE', 'RESTORED_ONLINE')
GROUP BY p.id, p.status;
