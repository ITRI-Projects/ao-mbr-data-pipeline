-- March 24 through April 23, 2026 (inclusive)
SELECT
    target.[DATA_ID] AS [Target_DATA_ID],
    target.[DATA_DATE],
    target.[DATA_TIME],

    -- Target: A2 methanol dosing flow
    target.[FQ_CH3OH] AS [Target_FQ_CH3OH],

    -- Flow
    flow.[A2_Qinto],

    -- A2 influent measurements and recycle flow
    target.[COD_in] AS [A2_COD_in],
    target.[Q_r1]   AS [A2_Q_r1],
    target.[NH3_N]  AS [A2_NH3_N],

    -- A2 process measurements
    process_a2.[PH]   AS [A2_PH],
    process_a2.[ORP]  AS [A2_ORP],
    process_a2.[DO]   AS [A2_DO],
    process_a2.[MLSS] AS [A2_MLSS],

    -- Effluent measurements
    effluent.[NH4_N] AS [Effluent_NH4_N],
    effluent.[NO3_N] AS [Effluent_NO3_N]

FROM [ITRI].[dbo].[T02_06A2_SCADA] AS target

LEFT JOIN [ITRI].[dbo].[T02_0506A_SCADA] AS flow
    ON flow.[DATA_DATE] = target.[DATA_DATE]
   AND flow.[DATA_TIME] = target.[DATA_TIME]

LEFT JOIN [ITRI].[dbo].[T02_06A2_RealData] AS process_a2
    ON process_a2.[DATA_DATE] = target.[DATA_DATE]
   AND process_a2.[DATA_TIME] = target.[DATA_TIME]

LEFT JOIN [ITRI].[dbo].[T02_08A_SCADA] AS effluent
    ON effluent.[DATA_DATE] = target.[DATA_DATE]
   AND effluent.[DATA_TIME] = target.[DATA_TIME]

WHERE target.[DATA_DATE] >= '20260324'
  AND target.[DATA_DATE] <  '20260424'

ORDER BY target.[DATA_DATE], target.[DATA_TIME];
