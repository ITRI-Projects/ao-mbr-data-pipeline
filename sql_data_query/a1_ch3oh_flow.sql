-- March 24 through April 23, 2026 (inclusive)
SELECT
    target.[DATA_ID] AS [Target_DATA_ID],
    target.[DATA_DATE],
    target.[DATA_TIME],

    -- Target: A1 methanol dosing flow
    target.[FQ_CH3OH] AS [Target_A1_FQ_CH3OH],

    -- Flow
    flow.[A1_Qinto],

    -- A1 influent measurements and recycle flow
    target.[COD_in] AS [A1_COD_in],
    target.[Q_r1]   AS [A1_Q_r1],
    target.[NH3_N]  AS [A1_NH3_N],

    -- A1 process measurements
    process_a1.[PH]   AS [A1_A_PH],
    process_a1.[ORP]  AS [A1_A_ORP],
    process_a1.[DO]   AS [A1_A_DO],
    process_a1.[MLSS] AS [A1_A_MLSS],

    -- Effluent measurements
    effluent.[NH4_N] AS [Effluent_NH4_N],
    effluent.[NO3_N] AS [Effluent_NO3_N]

FROM [ITRI].[dbo].[T02_06A1_SCADA] AS target

LEFT JOIN [ITRI].[dbo].[T02_0506A_SCADA] AS flow
    ON flow.[DATA_DATE] = target.[DATA_DATE]
   AND flow.[DATA_TIME] = target.[DATA_TIME]

LEFT JOIN [ITRI].[dbo].[T02_06A1_RealData] AS process_a1
    ON process_a1.[DATA_DATE] = target.[DATA_DATE]
   AND process_a1.[DATA_TIME] = target.[DATA_TIME]

LEFT JOIN [ITRI].[dbo].[T02_08A_SCADA] AS effluent
    ON effluent.[DATA_DATE] = target.[DATA_DATE]
   AND effluent.[DATA_TIME] = target.[DATA_TIME]

WHERE target.[DATA_DATE] >= '20260324'
  AND target.[DATA_DATE] <  '20260424'

ORDER BY target.[DATA_DATE], target.[DATA_TIME];
