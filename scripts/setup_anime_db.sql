-- Create anime database schema
DROP TABLE IF EXISTS anime CASCADE;
DROP TABLE IF EXISTS studios CASCADE;

-- Create studios table
CREATE TABLE studios (
    studio_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    founded_year INTEGER,
    country VARCHAR(50),
    website VARCHAR(255)
);

-- Create anime table
CREATE TABLE anime (
    anime_id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    title_english VARCHAR(255),
    type VARCHAR(20) CHECK (type IN ('TV', 'Movie', 'OVA', 'ONA', 'Special')),
    episodes INTEGER,
    status VARCHAR(20) CHECK (status IN ('Finished Airing', 'Currently Airing', 'Not yet aired')),
    aired_from DATE,
    aired_to DATE,
    studio_id INTEGER REFERENCES studios(studio_id),
    source VARCHAR(50),
    genre VARCHAR(255),
    duration_minutes INTEGER,
    rating VARCHAR(20),
    score DECIMAL(3, 2) CHECK (score >= 0 AND score <= 10),
    ranked INTEGER,
    popularity INTEGER,
    members INTEGER,
    synopsis TEXT
);

-- Insert studios data
INSERT INTO studios (name, founded_year, country, website) VALUES
('Studio Ghibli', 1985, 'Japan', 'https://www.ghibli.jp'),
('Madhouse', 1972, 'Japan', 'https://www.madhouse.co.jp'),
('Wit Studio', 2012, 'Japan', 'https://witstudio.co.jp'),
('Bones', 1998, 'Japan', 'https://www.bones.co.jp'),
('A-1 Pictures', 2005, 'Japan', 'https://a1p.jp'),
('Ufotable', 2000, 'Japan', 'https://www.ufotable.com'),
('Kyoto Animation', 1985, 'Japan', 'https://www.kyotoanimation.co.jp'),
('Production I.G', 1987, 'Japan', 'https://www.production-ig.co.jp'),
('CloverWorks', 2018, 'Japan', 'https://cloverworks.co.jp'),
('MAPPA', 2011, 'Japan', 'https://www.mappa.co.jp');

-- Insert anime data
INSERT INTO anime (title, title_english, type, episodes, status, aired_from, aired_to, studio_id, source, genre, duration_minutes, rating, score, ranked, popularity, members, synopsis) VALUES
('Sen to Chihiro no Kamikakushi', 'Spirited Away', 'Movie', 1, 'Finished Airing', '2001-07-20', '2001-07-20', 1, 'Original', 'Adventure, Supernatural', 125, 'PG', 8.78, 28, 52, 1725000, 'Ten-year-old Chihiro and her parents are traveling to their new home when her father takes a wrong turn.'),
('Mononoke Hime', 'Princess Mononoke', 'Movie', 1, 'Finished Airing', '1997-07-12', '1997-07-12', 1, 'Original', 'Action, Adventure, Fantasy', 134, 'PG-13', 8.66, 67, 131, 1044000, 'When an Emishi village is attacked by a fierce demon boar, the young prince Ashitaka risks his life to defend his tribe.'),
('Death Note', 'Death Note', 'TV', 37, 'Finished Airing', '2006-10-04', '2007-06-27', 2, 'Manga', 'Supernatural, Suspense', 23, 'R', 8.62, 75, 2, 3645000, 'A high school student named Light Yagami discovers a mysterious notebook that has the power to kill anyone whose name is written in it.'),
('Shingeki no Kyojin', 'Attack on Titan', 'TV', 25, 'Finished Airing', '2013-04-07', '2013-09-29', 3, 'Manga', 'Action, Drama, Fantasy', 24, 'R', 8.54, 110, 1, 3800000, 'Humanity is forced to live in cities surrounded by three enormous walls due to the Titans, gigantic humanoid creatures who devour humans.'),
('Fullmetal Alchemist: Brotherhood', 'Fullmetal Alchemist: Brotherhood', 'TV', 64, 'Finished Airing', '2009-04-05', '2010-07-04', 4, 'Manga', 'Action, Adventure, Drama, Fantasy', 24, 'R', 9.10, 1, 3, 3115000, 'Two brothers use alchemy to try to resurrect their mother, but the attempt fails, leaving them physically deformed.'),
('Sword Art Online', 'Sword Art Online', 'TV', 25, 'Finished Airing', '2012-07-08', '2012-12-23', 5, 'Light Novel', 'Adventure, Romance, Fantasy', 23, 'PG-13', 7.21, 2900, 5, 2415000, 'In the year 2022, thousands of people get trapped in a new virtual MMORPG and the only way to escape is to clear its 100 floors.'),
('Kimetsu no Yaiba', 'Demon Slayer', 'TV', 26, 'Finished Airing', '2019-04-06', '2019-09-28', 6, 'Manga', 'Action, Historical, Supernatural', 23, 'R', 8.45, 160, 15, 2850000, 'Young Tanjirou returns home to find his family slaughtered by a demon. His younger sister Nezuko is the sole survivor but has been transformed into a demon herself.'),
('Violet Evergarden', 'Violet Evergarden', 'TV', 13, 'Finished Airing', '2018-01-11', '2018-04-05', 7, 'Light Novel', 'Drama, Fantasy, Slice of Life', 24, 'PG-13', 8.67, 64, 178, 1452000, 'After the war, Violet Evergarden begins a new life at the CH Postal Company, working as an Auto Memory Doll to help others express their feelings through letters.'),
('Psycho-Pass', 'Psycho-Pass', 'TV', 22, 'Finished Airing', '2012-10-12', '2013-03-22', 8, 'Original', 'Action, Sci-Fi, Suspense', 23, 'R', 8.34, 246, 89, 1735000, 'In a futuristic world where a computer system can measure a persons mental state and probability of committing crimes, a new inspector must learn to work within the system.'),
('Spy x Family', 'Spy x Family', 'TV', 12, 'Finished Airing', '2022-04-09', '2022-06-25', 3, 'Manga', 'Action, Comedy', 24, 'PG-13', 8.51, 122, 48, 1465000, 'A spy must build a fake family to execute a mission, not knowing that the girl he adopts as his daughter is a telepath, and the woman he agrees to be his wife is a skilled assassin.'),
('Bocchi the Rock!', 'Bocchi the Rock!', 'TV', 12, 'Finished Airing', '2022-10-09', '2022-12-25', 9, 'Manga', 'Comedy, Music', 24, 'PG-13', 8.78, 27, 285, 425000, 'Hitori Gotou is a high school girl whos starting to learn to play the guitar because she dreams of being in a band, but shes so shy that she hasnt made a single friend.'),
('Jujutsu Kaisen', 'Jujutsu Kaisen', 'TV', 24, 'Finished Airing', '2020-10-03', '2021-03-27', 10, 'Manga', 'Action, School, Supernatural', 24, 'R', 8.49, 130, 34, 2145000, 'Yuuji Itadori eats a cursed finger and becomes the host of a powerful curse. He joins Tokyo Jujutsu High School to learn to control his power and help defeat other curses.'),
('Chainsaw Man', 'Chainsaw Man', 'TV', 12, 'Finished Airing', '2022-10-12', '2022-12-28', 10, 'Manga', 'Action, Supernatural', 24, 'R', 8.47, 145, 72, 1324000, 'Denji is a teenage boy living with a Chainsaw Devil named Pochita. Due to his debts, hes living a rough life and doing anything for money, until hes betrayed and killed.'),
('Howl no Ugoku Shiro', 'Howls Moving Castle', 'Movie', 1, 'Finished Airing', '2004-11-20', '2004-11-20', 1, 'Novel', 'Adventure, Drama, Fantasy, Romance', 119, 'G', 8.66, 68, 84, 1265000, 'Sophie, a young milliner, is turned into an elderly woman by a witch. She encounters a wizard named Howl and gets caught up in his resistance to fighting for the king.'),
('Steins;Gate', 'Steins;Gate', 'TV', 24, 'Finished Airing', '2011-04-06', '2011-09-14', 3, 'Visual Novel', 'Sci-Fi, Suspense', 24, 'PG-13', 8.76, 35, 13, 2528000, 'Rintarou Okabe is a self-proclaimed mad scientist who discovers time travel through a microwave and must prevent a dystopian future.');

-- Create indexes for better query performance
CREATE INDEX idx_anime_studio ON anime(studio_id);
CREATE INDEX idx_anime_type ON anime(type);
CREATE INDEX idx_anime_status ON anime(status);
CREATE INDEX idx_anime_score ON anime(score);
CREATE INDEX idx_anime_popularity ON anime(popularity);