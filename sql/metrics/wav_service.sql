-- Metric: wav_service
-- Questions: Q11
-- Params: none
-- Grain: month × mode; uber and lyft
-- Columns: month, mode, trips, wav_requests, wav_trips, wav_share
-- Source: TLC trip records
--
-- D29. Trip records hold completed trips only, so a WAV match rate can't be measured.
-- trips = valid trips; wav_requests = completed trips that requested a wheelchair-accessible
-- vehicle; wav_trips = valid trips that ran in one, requested or not;
-- wav_share = SUM(wav_trips) ÷ SUM(trips_valid).
SELECT month,
       mode,
       SUM(trips_valid)::BIGINT AS trips,
       SUM(wav_req)::BIGINT AS wav_requests,
       SUM(wav_trips)::BIGINT AS wav_trips,
       SUM(wav_trips) / NULLIF(SUM(trips_valid), 0) AS wav_share
FROM agg_zone_hour
WHERE mode IN ('uber', 'lyft')
GROUP BY month, mode
ORDER BY month, mode;
