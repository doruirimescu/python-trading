USE trading;

SET time_zone = '+00:00';

INSERT INTO swaps(date_added, instrument, accumulated_swap)
VALUES
    ('2023-02-19', 'CHFHUF', 1.76),
    ('2023-02-19', 'CHFHUF', 1.32),
    ('2023-02-19', 'CHFHUF', 1.32),
    ('2023-02-19', 'CHFHUF', 5.83),

    ('2023-02-18', 'CHFHUF', 1.32),
    ('2023-02-18', 'CHFHUF', 0.88),
    ('2023-02-18', 'CHFHUF', 5.38),
    ('2023-02-18', 'CHFHUF', 0.88),

    ('2023-02-17', 'CHFHUF', 0.44),
    ('2023-02-17', 'CHFHUF', 0.88),
    ('2023-02-17', 'CHFHUF', 0.44),
    ('2023-02-17', 'CHFHUF', 4.95),

    ('2023-02-16', 'CHFHUF', 4.51),
    ('2023-02-16', 'CHFHUF', 0.44),

    ('2023-02-15', 'CHFHUF', 4.07),

    ('2023-02-14', 'CHFHUF', 3.63),
    ('2023-02-14', 'CHFHUF', 3.63)
;


SELECT * FROM swaps;

SELECT
  date_added,
  instrument,
  accumulated_swap
FROM
  trading.swaps
WHERE date_added=CURRENT_DATE;
