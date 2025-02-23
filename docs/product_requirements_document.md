# AI Culture Concierge – Product Requirements Document

## 1. App Overview

The **AI Culture Concierge** is a web application (with optional SMS and email interfaces) that helps users discover, explore, and attend cultural events—primarily music concerts and film showings in **New York City** (v1 scope). The system aggregates event details by scraping a curated list of venue websites and storing that information in a database. Users can:
- Filter events according to their neighborhoods, genres, or Spotify libraries.
- Chat with an AI-powered concierge to get personalized recommendations.
- Receive weekly event bulletins via email.
- Follow links to purchase tickets or add events to their calendars.

The aesthetic style is minimal and modern, **inspired by ECM records**. Future versions will expand coverage to multiple metros.

### Core Objectives
1. **Automate Event Aggregation**: Continuously scrape venue sites to populate the database with upcoming events.
2. **Personalized Discovery**: Enable user preference filtering (e.g., neighborhoods, genres, Spotify music profile).
3. **AI Chat Concierge**: Provide a conversational interface (web chat, SMS, email) that suggests events from the database based on user queries.
4. **Email Bulletins**: Send weekly curated bulletins (Sundays) via email with recommended events.
5. **Marketing Attribution**: Append tracking parameters to outbound links to identify the originating traffic.

### References
- [Spotify OAuth documentation](https://developer.spotify.com/documentation/general/guides/authorization/)  
- [Flask documentation for web app structure](https://flask.palletsprojects.com/)  
- [SQLAlchemy ORM patterns](https://docs.sqlalchemy.org/en/14/orm/)  


## 2. User Flow

1. **Landing / Home Page**  
   - Unauthenticated users see a list of upcoming events (default recommended or trending).
   - Option to sign in with Spotify or continue browsing anonymously.

2. **Sign-In (Spotify OAuth)**  
   - User clicks “Login with Spotify”.
   - Redirected to Spotify’s OAuth flow.
   - Upon successful authentication, returned to app with user’s Spotify token stored in the database.

3. **Event Browsing**  
   - User sees event cards sorted by date.
   - Each card shows event name (or performer), date, time, venue, link to tickets, calendar link, and details.

4. **Filtering & Preferences**  
   - User visits Preferences page to select favorite neighborhoods, favorite venues, or genres.
   - If Spotify-synced, the app merges user’s library or top artists with the event database for potential matches.

5. **Event Recommendation (AI Concierge)**  
   - User opens chat (web chat window, SMS, or email) and asks for suggestions (e.g., “Which jazz shows are happening Friday night in the East Village?”).
   - The system queries the DB and responds with curated listings.

6. **Weekly Email Bulletin**  
   - If user opts in, they receive a Sunday email with recommended events for the coming week.

7. **Outbound Ticket Link**  
   - When user clicks “Tickets”, link is appended with marketing parameters (e.g., `?utm_source=aicc_app`).

### References
- [Spotipy usage for reading user library info](https://spotipy.readthedocs.io/)  
- [Twilio SMS integration guide (if using Twilio)](https://www.twilio.com/docs/sms)  
- [SendGrid email marketing & bulletins (if using SendGrid)](https://docs.sendgrid.com/)  


## 3. Tech Stack & APIs

### Front-End
- **Framework**: HTML/CSS/JS with minimal styling (ECM-inspired). Potential for a lightweight front-end framework (e.g., minimal React or Vue) for chat widget if needed.
- **Styling**: A custom CSS theme with a black/gray/white color palette, referencing ECM aesthetics.

### Back-End
- **Language**: Python (Flask framework).
- **Database**: SQLite or PostgreSQL. (The prototype uses SQLite, but production could use PostgreSQL.)
- **ORM**: SQLAlchemy for data modeling.

### Scraping & Data Collection
- **Tools**: 
  - **Requests + BeautifulSoup** (and occasionally **Selenium**) for custom scrapers.
  - **Firecrawl** for general-purpose scraping.
- **Schedule**: Python `schedule` library for daily scraping tasks.

### AI/ML Services
- **OpenAI** (or local LLM approach) to handle advanced conversational queries.

### Authentication
- **Spotify OAuth** for user login and preference building via `spotipy`.

### Potential 3rd Party APIs
- **SendGrid** (or Amazon SES) for sending weekly bulletins.
- **Twilio** (or similar) for SMS-based chatbot.

### References
- [Flask + SQLAlchemy application patterns](https://flask.palletsprojects.com/en/2.2.x/patterns/sqlalchemy/)  
- [Selenium Python docs](https://selenium-python.readthedocs.io/)  
- [Firecrawl PyPi page](https://pypi.org/project/firecrawl-py/)  


## 4. Core Features

1. **Event Aggregation / Scraping**
   - **Automated Scrapers**: For each venue, a custom or generic scraper fetches upcoming events and details (artist, date, times, ticket links).
   - **Storage**: Data stored in `Concerts`, `Venues`, `Artists`, and `Times` tables.

2. **User Accounts & Preferences**
   - **Spotify OAuth**: Import top artists, saved tracks, or followed artists to rank relevant events.
   - **Manual Preferences**: Neighborhoods, venues, and genres stored in user profile.

3. **Event Display & Filtering**
   - **Dynamic Listing**: Filter by date range (by default show next 90 days).
   - **Advanced Filter**: Combine user preferences (venues, neighborhoods, genres, and any relevant Spotify matches).

4. **AI Concierge Chat**
   - **Natural Language Query**: “What’s going on next Saturday near Bushwick?” → system returns relevant DB events.
   - **Multi-Channel**: 
     - Web-based chat widget
     - SMS conversation
     - Email-based Q&A
   - **Template-based prompting**: DB rows are fed into an LLM prompt.

5. **Weekly Bulletin**
   - **Curated Email**: Sent on Sundays for the upcoming week’s events, sorted by user’s preference & potential Spotify matches.
   - **Single-Click Unsubscribe**.

6. **Calendar & Ticket Integration**
   - **Calendar Links**: ICS file or Google Calendar link generation for each event card.
   - **Ticket Link**: Outbound link with appended UTM params for marketing attribution.

### References
- [ICS calendar format docs](https://icalendar.org/)  
- [Google Calendar event link format](https://developers.google.com/calendar/api)  

## 5. In-Scope and Out-of-Scope

### In-Scope (v1)
- **NYC Venues Only**: Hardcoded or curated list of 50+ major clubs, jazz bars, film theaters, etc.
- **Manual Genre & Neighborhood** mapping for known venues.
- **Basic ChatBot**: Summaries from event DB, no advanced personalization beyond user’s preferences.
- **Email Bulletin**: Basic templated email, only weekly frequency.
- **Mobile-Responsive**: The web interface must adapt well to mobile screens.

### Out-of-Scope (v1)
- **Multiple Metros**: Expansions beyond NYC (planned for future releases).
- **Internationalization**: English only for text content.
- **Complex E-commerce**: We do not handle direct ticket purchases or payment; we only redirect externally.
- **Deep AI Recommendation**: v1 is limited to rule-based filtering plus basic query parsing with an LLM. No advanced collaborative filtering or real-time personalization.

### References
- [Basic rule-based recommendation approach](https://towardsdatascience.com/basics-of-rule-based-recommender-systems-797b0e9e6f6d)  

## 6. Non-Functional Requirements

1. **Performance**  
   - Scraping tasks must complete daily without overloading the hosting environment or exceeding third-party rate limits (e.g., Firecrawl limit ~3000 pages/month).
   - Page load time for the main listing page under 3 seconds for typical usage.

2. **Reliability & Availability**  
   - Automatic daily scraping: if a particular scraper fails, it retries the next day.  
   - Weekly email bulletins run automatically (Sunday). No single point of failure for that job.

3. **Security**  
   - Spotify OAuth tokens stored securely (encrypted at rest).
   - HTTPS enforced for all user interactions.

4. **Usability**  
   - Minimal, clean UI with ECM-like design.  
   - Simple onboarding: one-click login with Spotify or skip.  

5. **Scalability**  
   - Database can handle thousands of events.  
   - If expanded to multiple cities, must handle up to 10x more scrapes or specialized concurrency management.

6. **Maintainability**  
   - Maintain a modular codebase (one file per scraper).  
   - Centralized logging for scraping tasks.

### References
- [OWASP Security best practices](https://owasp.org/)  
- [Flask secure deployment guidelines](https://flask.palletsprojects.com/en/2.2.x/deploying/)  

## 7. Constraints & Assumptions

1. **Data Source Constraints**  
   - Some venues have complex or JavaScript-heavy sites requiring Selenium. Others can be scraped with standard `requests`/`BeautifulSoup`.
   - Firecrawl usage is limited by a monthly credit cap.

2. **Rate Limiting**  
   - Must honor remote sites’ rate-limit policies (e.g., not scraping any single site more than once per day).

3. **User Privacy**  
   - We only store minimal user data (email, user preferences, and Spotify tokens).  
   - No usage analytics beyond standard server logs.

4. **Scheduling**  
   - The main scraping routine runs daily around 4 AM ET.  
   - The weekly bulletin runs every Sunday morning.

5. **Infrastructure**  
   - Hosted on a standard VPS or cloud environment, supporting Python + cron-like scheduling.

### References
- [Tenacity library for robust retry logic](https://github.com/jd/tenacity)  

## 8. Known Issues & Potential Pitfalls

1. **Scraper Fragility**  
   - Venue websites change their structure or layout, breaking scrapers. Must monitor or re-check them frequently.

2. **Exceeding Firecrawl Credits**  
   - If usage spikes, we may hit monthly scraping limits or get 429 errors.

3. **Data Quality & Duplicates**  
   - Some events might appear twice across multiple sources. Need to deduplicate carefully.

4. **Limited Personalization**  
   - v1 depends heavily on user preferences and basic matching of Spotify artist names. Fuzzy matching might be inaccurate.

5. **Spam Filtering on Weekly Emails**  
   - Must ensure email deliverability (proper DKIM, SPF, DMARC records).

6. **High Latency with LLM**  
   - If the AI concierge is integrated with a remote LLM, queries may take longer to return.  
   - Must consider caching or partial pre-computation.

7. **User Opt-Out**  
   - Need an easy unsubscribe flow for weekly bulletins and SMS messages (to comply with CAN-SPAM, TCPA, etc.).

### References
- [CAN-SPAM compliance overview](https://www.ftc.gov/business-guidance/resources/can-spam-act-compliance-guide-business)  
- [TCPA compliance for SMS](https://www.fcc.gov/general/telemarketing-and-robocalls)  

---

**End of Document**  