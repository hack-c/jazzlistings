-- First, let's see what we're dealing with
SELECT DISTINCT name FROM artists 
WHERE name IN ('TBA', 'Artist Name') 
   OR name LIKE '%TBA%'
   OR name = ''
   OR name IS NULL;

-- Then delete the concerts linked to these artists
DELETE FROM concert_artists 
WHERE artist_id IN (
    SELECT id FROM artists 
    WHERE name IN ('TBA', 'Artist Name')
    OR name LIKE '%TBA%'
    OR name = ''
    OR name IS NULL
);

-- Finally delete the artists themselves
DELETE FROM artists 
WHERE name IN ('TBA', 'Artist Name')
OR name LIKE '%TBA%'
OR name = ''
OR name IS NULL; 