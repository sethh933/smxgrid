-- Support the first-correct guess lookup by rider and correctness.
IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE object_id = OBJECT_ID(N'dbo.UserGuesses', N'U')
      AND name = N'IX_UserGuesses_RiderID_IsCorrect'
)
BEGIN
    CREATE NONCLUSTERED INDEX IX_UserGuesses_RiderID_IsCorrect
        ON dbo.UserGuesses (RiderID, IsCorrect);
END;
