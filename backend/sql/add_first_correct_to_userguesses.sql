IF COL_LENGTH('dbo.UserGuesses', 'IsFirstCorrect') IS NULL
BEGIN
    ALTER TABLE dbo.UserGuesses
    ADD IsFirstCorrect BIT NOT NULL
        CONSTRAINT DF_UserGuesses_IsFirstCorrect DEFAULT (0);
END;
