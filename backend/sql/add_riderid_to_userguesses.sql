SET XACT_ABORT ON;

BEGIN TRY
    BEGIN TRANSACTION;

    IF COL_LENGTH('dbo.UserGuesses', 'RiderID') IS NULL
    BEGIN
        ALTER TABLE dbo.UserGuesses
        ADD RiderID INT NULL;
    END;

    UPDATE ug
    SET ug.RiderID = rl.RiderID
    FROM dbo.UserGuesses ug
    JOIN dbo.Rider_List rl
        ON rl.FullName = ug.FullName
    WHERE ug.RiderID IS NULL;

    IF EXISTS (
        SELECT 1
        FROM dbo.UserGuesses
        WHERE RiderID IS NULL
    )
    BEGIN
        THROW 51000, 'Backfill failed: some UserGuesses rows still have NULL RiderID values. Check FullName matches in Rider_List before re-running.', 1;
    END;

    ALTER TABLE dbo.UserGuesses
    ALTER COLUMN RiderID INT NOT NULL;

    IF NOT EXISTS (
        SELECT 1
        FROM sys.indexes
        WHERE name = 'IX_UserGuesses_RiderID'
          AND object_id = OBJECT_ID('dbo.UserGuesses')
    )
    BEGIN
        CREATE INDEX IX_UserGuesses_RiderID
            ON dbo.UserGuesses (RiderID);
    END;

    IF NOT EXISTS (
        SELECT 1
        FROM sys.foreign_keys
        WHERE name = 'FK_UserGuesses_Rider_List_RiderID'
    )
    BEGIN
        ALTER TABLE dbo.UserGuesses
        ADD CONSTRAINT FK_UserGuesses_Rider_List_RiderID
            FOREIGN KEY (RiderID) REFERENCES dbo.Rider_List (RiderID);
    END;

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0
        ROLLBACK TRANSACTION;

    THROW;
END CATCH;
