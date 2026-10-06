USE [ITRI];
GO

SET XACT_ABORT ON;

IF USER_ID(N'admin') IS NULL
    THROW 50001, 'Database user admin does not exist in ITRI.', 1;

BEGIN TRY
    BEGIN TRANSACTION;

    IF OBJECT_ID(N'dbo.CleanedSensorData', N'U') IS NULL
    BEGIN
        CREATE TABLE [dbo].[CleanedSensorData] (
            [datetime] DATETIME2(6) NOT NULL,
            [A1_Qin] FLOAT NULL,
            [A2_Qin] FLOAT NULL,
            [A1_COD_in] FLOAT NULL,
            [A1_FQ_CH3OH] FLOAT NULL,
            [A1_Q_r1] FLOAT NULL,
            [A2_COD_in] FLOAT NULL,
            [A2_Q_r1] FLOAT NULL,
            [A2_FQ_CH3OH] FLOAT NULL,
            [A1_NH3_N] FLOAT NULL,
            [A2_NH3_N] FLOAT NULL,
            [A1_A_PH] FLOAT NULL,
            [A1_A_ORP] FLOAT NULL,
            [A1_A_DO] FLOAT NULL,
            [A1_A_MLSS] FLOAT NULL,
            [A2_A_PH] FLOAT NULL,
            [A2_A_ORP] FLOAT NULL,
            [A2_A_DO] FLOAT NULL,
            [A2_A_MLSS] FLOAT NULL,
            [A1_O_PH] FLOAT NULL,
            [A1_O_ORP] FLOAT NULL,
            [A1_O_DO] FLOAT NULL,
            [A1_O_MLSS] FLOAT NULL,
            [A2_O_PH] FLOAT NULL,
            [A2_O_ORP] FLOAT NULL,
            [A2_O_DO] FLOAT NULL,
            [A2_O_MLSS] FLOAT NULL,
            [Q_A1_air] FLOAT NULL,
            [Q_A2_air] FLOAT NULL,
            [Eff_NH4_N] FLOAT NULL,
            [Eff_NO3_N] FLOAT NULL,
            CONSTRAINT [PK_CleanedSensorData] PRIMARY KEY ([datetime])
        );
        PRINT 'Created dbo.CleanedSensorData.';
    END
    ELSE
        PRINT 'dbo.CleanedSensorData already exists; its structure and data were preserved.';

    -- INSERT also makes the table visible to the importer's OBJECT_ID lookup.
    GRANT INSERT ON OBJECT::[dbo].[CleanedSensorData] TO [admin];

    COMMIT TRANSACTION;
    PRINT 'Insert access granted to admin. You can now run make load.';
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0
        ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO
