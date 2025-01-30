from crawler import Crawler
from parser import parse_markdown
from database import Session, init_db
from models import Artist, Venue, Concert
from datetime import datetime


def main():
    """
    Main function that orchestrates the crawling, parsing, and storing of concert data.
    """
    # Initialize the database
    init_db()
    session = Session()

    # List of venue websites to crawl
    venues = [
            {'name': 'Village Vanguard', 'url': 'https://villagevanguard.com/'},
            {'name': 'Smalls Jazz Club', 'url': 'https://smallslive.com/'},
            {'name': 'Mezzrow Jazz Club', 'url': 'https://mezzrow.com/'},
            {'name': 'Dizzy\'s Club', 'url': 'https://jazz.org/dizzys-club/'},
            {'name': 'The Jazz Gallery', 'url': 'https://jazzgallery.org/calendar/'},
            {'name': 'Blue Note', 'url': 'https://www.bluenotejazz.com/'},
            {'name': 'Ornithology Jazz Club', 'url': 'https://www.ornithologyjazzclub.com/events-2/'},
            {'name': 'Ornithology Cafe', 'url': 'https://www.ornithologyjazzclub.com/new-page-1/'},
            {'name': 'Bar LunÀtico', 'url': 'https://www.barlunatico.com/music/'},
            {'name': 'Bar Bayeux', 'url': 'https://www.barbayeux.com/jazz/'},
            {'name': 'Marians Jazz Room', 'url': 'https://www.mariansbrooklyn.com/events'},
            {'name': 'The Owl Music Parlor', 'url': 'https://theowl.nyc/calendar/'},
            {'name': 'Zinc Bar', 'url': 'https://zincbar.com/'},
            {'name': 'Mona\'s', 'url': 'https://www.monascafenyc.com/'},
            {'name': 'The Stone', 'url': 'http://thestonenyc.com/calendar.php'},
            {'name': 'Abrons Art Center', 'url': 'https://abronsartscenter.org/calendar'},
            {'name': 'Café Erzulie', 'url': 'https://www.cafeerzulie.com/events'},
            {'name': 'Nublu 151', 'url': 'https://nublu.net/program'},
            # {'name': 'Cellar Dog', 'url': 'https://cellardog.net/'},
            {'name': 'Umbra Café', 'url': 'https://www.umbrabrooklyn.com/events'},
            {'name': 'Arthur\'s Tavern', 'url': 'https://arthurstavern.nyc/events/'},
            {'name': 'Birdland', 'url': 'https://www.birdlandjazz.com/'},
            # {'name': 'Bill\'s Place', 'url': 'https://www.billsplaceharlem.com/'},
            {'name': 'Barbès', 'url': 'https://www.barbesbrooklyn.com/events'},
            {'name': 'Smoke Jazz & Supper Club', 'url': 'https://livestreams.smokejazz.com/'},
            {'name': 'Room 623 at B2 Harlem', 'url': 'https://www.room623.com/tickets'},
            {'name': 'Soapbox Gallery', 'url': 'https://www.soapboxgallery.org/calendar'},
            {'name': 'Silvana', 'url': 'https://silvana-nyc.com/calendar.php'},
            {'name': 'Sistas\' Place', 'url': 'https://sistasplace.org/'},
            {'name': 'Drom', 'url': 'https://dromnyc.com/events/'},
            {'name': 'Roulette', 'url': 'https://roulette.org/calendar/'},
            {'name': 'Jazzmobile', 'url': 'https://jazzmobile.org/'},
            {'name': 'The Django', 'url': 'https://www.thedjangonyc.com/events'},
            {'name': 'Pangea', 'url': 'https://www.pangeanyc.com/music/'},
            {'name': 'The Ear Inn', 'url': 'https://www.theearinn.com/music-schedule/'},
            {'name': 'Shrine', 'url': 'https://shrinenyc.com/'},
            {'name': 'Chelsea Table + Stage', 'url': 'https://www.chelseatableandstage.com/tickets-shows'},
            {'name': 'The Keep', 'url': 'https://www.thekeepny.com/calendar'},
            {'name': 'Joe\'s Pub', 'url': 'https://publictheater.org/joes-pub/'},
            {'name': 'Klavierhaus', 'url': 'https://event.klavierhaus.com/k/calendar'},
            {'name': 'Saint Peter\'s Church', 'url': 'https://www.saintpeters.org/events'},
            {'name': 'Minton\'s Playhouse', 'url': 'https://www.eventbrite.com/o/mintons-playhouse-76715695933'},
            {'name': 'National Sawdust', 'url': 'https://www.nationalsawdust.org/performances-prev'},
            {'name': 'The Cutting Room', 'url': 'https://thecuttingroomnyc.com/calendar/'},
            {'name': 'Swing 46', 'url': 'https://swing46.nyc/calendar/'},
            {'name': 'The Appel Room', 'url': 'https://www.lincolncenter.org/venue/the-appel-room/v/calendar'},
            {'name': 'Symphony Space', 'url': 'https://www.symphonyspace.org/events'},
            {'name': 'Le Poisson Rouge', 'url': 'https://www.lpr.com/'},
    ]

    crawler = Crawler()

    for venue_info in venues:
        venue_name = venue_info['name']
        venue_url = venue_info['url']
        print(f"Scraping {venue_name} at {venue_url}")
        # Scrape the venue website
        markdown_content = crawler.scrape_venue(venue_url)
        if markdown_content:
            print("Parsing markdown content")
            # Parse the markdown content to extract concert data
            concert_data_list = parse_markdown(markdown_content)
            if concert_data_list:
                print("Storing concert data")
                # Store the concert data in the database
                store_concert_data(session, concert_data_list, venue_info)
            else:
                print("Failed to parse concert data")
        else:
            print("Failed to scrape markdown content")

    session.close()


def store_concert_data(session, concert_data_list, venue_info):
    """
    Stores the concert data into the database.

    Parameters:
        session: Database session.
        concert_data_list (list): List of concert data dictionaries.
        venue_info (dict): Venue information containing name and URL.
    """
    for concert_data in concert_data_list:
        # Data validation and cleaning
        try:
            artist_name = concert_data.get('artist', '').strip()
            date = concert_data.get('date', '').strip()
            time = concert_data.get('time', '').strip()

            if not artist_name or not date:
                print("Incomplete concert data (missing artist or date), skipping entry.")
                continue

            # If time is missing, assign a default time
            if not time:
                print(f"Time missing for concert on {date}. Assigning default time '20:00'.")
                time = "20:00"

            date_time_str = f"{date} {time}"
            try:
                date_time = datetime.strptime(date_time_str, "%Y-%m-%d %H:%M")
            except ValueError as ve:
                print(f"Invalid date/time format for concert on {date} at {time}: {ve}")
                continue

            venue_name = concert_data.get('venue', venue_info['name']).strip()
            address = concert_data.get('address', '').strip()
            ticket_link = concert_data.get('ticket_link', '').strip()
            price_range = concert_data.get('price_range', '').strip()
            special_notes = concert_data.get('special_notes', '').strip()

            # Get or create artist
            artist = session.query(Artist).filter_by(name=artist_name).first()
            if not artist:
                artist = Artist(name=artist_name)
                session.add(artist)
                session.commit()

            # Get or create venue
            venue = session.query(Venue).filter_by(name=venue_name).first()
            if not venue:
                venue = Venue(
                    name=venue_name, address=address, website_url=venue_info['url']
                )
                session.add(venue)
                session.commit()

            # Check if the concert already exists
            existing_concert = (
                session.query(Concert)
                .filter_by(venue_id=venue.id, date_time=date_time)
                .first()
            )
            if existing_concert:
                # Update existing concert if necessary
                if artist not in existing_concert.artists:
                    existing_concert.artists.append(artist)
                    session.commit()
            else:
                # Create new concert
                concert = Concert(
                    venue=venue,
                    date_time=date_time,
                    ticket_link=ticket_link,
                    price_range=price_range,
                    special_notes=special_notes,
                )
                concert.artists.append(artist)
                session.add(concert)
                session.commit()

        except Exception as e:
            print(f"Error storing concert data: {e}")
            continue


if __name__ == '__main__':
    main()
