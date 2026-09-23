-- March 24 through April 23, 2026 (inclusive)

SELECT
    target.[DATA_ID] AS [Target_DATA_ID],
    target.[DATA_DATE],
    target.[DATA_TIME],

    -- Target
    target.[NO3_N] AS [Target_NO3_N],

    -- Flow
    flow.[A1_Qinto],
    flow.[A2_Qinto],

    -- Influent measurements
    inlet_a1.[COD_in] AS [A1_COD_in],
    inlet_a2.[COD_in] AS [A2_COD_in],
    inlet_a1.[NH3_N]  AS [A1_NH3_N],
    inlet_a2.[NH3_N]  AS [A2_NH3_N],

    -- Methanol dosing
    inlet_a1.[FQ_CH3OH] AS [A1_FQ_CH3OH],
    inlet_a2.[FQ_CH3OH] AS [A2_FQ_CH3OH],

    -- Recycle flow and influent nitrate
    inlet_a1.[Q_r1]  AS [A1_Q_r1],
    inlet_a2.[Q_r1]  AS [A2_Q_r1],
    inlet_a1.[NO3_N] AS [A1_NO3_N],
    inlet_a2.[NO3_N] AS [A2_NO3_N],

    -- A1 process measurements
    process_a1.[PH]   AS [A1_PH],
    process_a1.[ORP]  AS [A1_ORP],
    process_a1.[DO]   AS [A1_DO],
    process_a1.[MLSS] AS [A1_MLSS],

    -- A2 process measurements
    process_a2.[PH]   AS [A2_PH],
    process_a2.[ORP]  AS [A2_ORP],
    process_a2.[DO]   AS [A2_DO],
    process_a2.[MLSS] AS [A2_MLSS],

    -- Aeration
    air.[Q_A1_Air],
    air.[Q_A2_Air],

    -- Effluent ammonia input
    target.[NH4_N] AS [Effluent_NH4_N]

FROM [ITRI].[dbo].[T02_08A_SCADA] AS target

LEFT JOIN [ITRI].[dbo].[T02_0506A_SCADA] AS flow
    ON flow.[DATA_DATE] = target.[DATA_DATE]
   AND flow.[DATA_TIME] = target.[DATA_TIME]

LEFT JOIN [ITRI].[dbo].[T02_06A1_SCADA] AS inlet_a1
    ON inlet_a1.[DATA_DATE] = target.[DATA_DATE]
   AND inlet_a1.[DATA_TIME] = target.[DATA_TIME]

LEFT JOIN [ITRI].[dbo].[T02_06A2_SCADA] AS inlet_a2
    ON inlet_a2.[DATA_DATE] = target.[DATA_DATE]
   AND inlet_a2.[DATA_TIME] = target.[DATA_TIME]

LEFT JOIN [ITRI].[dbo].[T02_06A1_RealData] AS process_a1
    ON process_a1.[DATA_DATE] = target.[DATA_DATE]
   AND process_a1.[DATA_TIME] = target.[DATA_TIME]

LEFT JOIN [ITRI].[dbo].[T02_06A2_RealData] AS process_a2
    ON process_a2.[DATA_DATE] = target.[DATA_DATE]
   AND process_a2.[DATA_TIME] = target.[DATA_TIME]

LEFT JOIN [ITRI].[dbo].[T02_07A_AIR] AS air
    ON air.[DATA_DATE] = target.[DATA_DATE]
   AND air.[DATA_TIME] = target.[DATA_TIME]

WHERE target.[DATA_DATE] >= '20260324'
  AND target.[DATA_DATE] <  '20260424'

ORDER BY target.[DATA_DATE], target.[DATA_TIME];