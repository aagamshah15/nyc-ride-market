-- Metric: wav_match_rate
-- Questions: Q11
-- Params: none
-- Grain: month × mode; uber and lyft
-- Columns: month, mode, requests, matched, match_rate
-- Source: TLC trip records
--
-- SPEC §6: wheelchair-accessible requests matched, SUM(wav_match) ÷ SUM(wav_req).
SELECT month,
       mode,
       SUM(wav_req)::BIGINT AS requests,
       SUM(wav_match)::BIGINT AS matched,
       SUM(wav_match) / NULLIF(SUM(wav_req), 0) AS match_rate
FROM agg_zone_hour
WHERE mode IN ('uber', 'lyft')
GROUP BY month, mode
ORDER BY month, mode;
