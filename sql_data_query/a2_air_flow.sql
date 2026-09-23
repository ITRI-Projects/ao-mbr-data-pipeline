-- March 24 through April 23, 2026 (inclusive)
SELECT
    target.[DATA_ID] AS [Target_DATA_ID],
    target.[DATA_DATE],
    target.[DATA_TIME],

    -- Target: A2 aeration flow rate
    target.[Q_A2_Air] AS [Target_Q_A2_Air],

    -- Flow
    flow.[A2_Qinto],

    -- A2 influent measurements, methanol dosing, and recycle flow
    inlet_a2.[COD_in]   AS [A2_COD_in],
    inlet_a2.[FQ_CH3OH] AS [A2_FQ_CH3OH],
    inlet_a2.[NH3_N]    AS [A2_NH3_N],
    inlet_a2.[Q_r1]     AS [A2_Q_r1],

    -- A2 process measurements
    process_a2.[ORP]  AS [A2_ORP],
    process_a2.[DO]   AS [A2_DO],
    process_a2.[MLSS] AS [A2_MLSS]

FROM [ITRI].[dbo].[T02_07A_AIR] AS target

LEFT JOIN [ITRI].[dbo].[T02_0506A_SCADA] AS flow
    ON flow.[DATA_DATE] = target.[DATA_DATE]
   AND flow.[DATA_TIME] = target.[DATA_TIME]

LEFT JOIN [ITRI].[dbo].[T02_06A2_SCADA] AS inlet_a2
    ON inlet_a2.[DATA_DATE] = target.[DATA_DATE]
   AND inlet_a2.[DATA_TIME] = target.[DATA_TIME]

LEFT JOIN [ITRI].[dbo].[T02_07A2_RealData] AS process_a2
    ON process_a2.[DATA_DATE] = target.[DATA_DATE]
   AND process_a2.[DATA_TIME] = target.[DATA_TIME]

WHERE target.[DATA_DATE] >= '20260324'
  AND target.[DATA_DATE] <  '20260424'

ORDER BY target.[DATA_DATE], target.[DATA_TIME];
