-- March 24 through April 23, 2026 (inclusive)
SELECT
    target.[DATA_ID] AS [Target_DATA_ID],
    target.[DATA_DATE],
    target.[DATA_TIME],

    -- Target: A1 aeration flow rate
    target.[Q_A1_Air] AS [Target_Q_A1_Air],

    -- Flow
    flow.[A1_Qinto],

    -- A1 influent measurements, methanol dosing, and recycle flow
    inlet_a1.[COD_in]   AS [A1_COD_in],
    inlet_a1.[FQ_CH3OH] AS [A1_FQ_CH3OH],
    inlet_a1.[NH3_N]    AS [A1_NH3_N],
    inlet_a1.[Q_r1]     AS [A1_Q_r1],

    -- A1 process measurements
    process_a1.[PH]   AS [A1_O_PH]
    process_a1.[ORP]  AS [A1_O_ORP],
    process_a1.[DO]   AS [A1_O_DO],
    process_a1.[MLSS] AS [A1_O_MLSS]

FROM [ITRI].[dbo].[T02_07A_AIR] AS target

LEFT JOIN [ITRI].[dbo].[T02_0506A_SCADA] AS flow
    ON flow.[DATA_DATE] = target.[DATA_DATE]
   AND flow.[DATA_TIME] = target.[DATA_TIME]

LEFT JOIN [ITRI].[dbo].[T02_06A1_SCADA] AS inlet_a1
    ON inlet_a1.[DATA_DATE] = target.[DATA_DATE]
   AND inlet_a1.[DATA_TIME] = target.[DATA_TIME]

LEFT JOIN [ITRI].[dbo].[T02_07A1_RealData] AS process_a1
    ON process_a1.[DATA_DATE] = target.[DATA_DATE]
   AND process_a1.[DATA_TIME] = target.[DATA_TIME]

WHERE target.[DATA_DATE] >= '20260324'
  AND target.[DATA_DATE] <  '20260424'

ORDER BY target.[DATA_DATE], target.[DATA_TIME];
