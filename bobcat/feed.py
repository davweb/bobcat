"""Generate RSS file"""

from feedgen.feed import FeedGenerator

RSS_FILE = 'podcast.xml'
LOGO_FILE = 'logo.png'

def create_rss_feed(episodes, podcast_path):
    """Create the RSS file for the episodes"""
    logo_url = f'{podcast_path}/{LOGO_FILE}'

    episodes = [episode for episode in episodes if episode.is_audio_downloaded()]
    publication_date = max(episode.published() for episode in episodes)

    feed_generator = FeedGenerator()
    feed_generator.load_extension('podcast')

    feed_generator.title('BBC Sounds Subscriptions')
    feed_generator.description('Episodes of shows I have subscribed to on BBC Sounds')
    feed_generator.author({'name': 'Bobcat'})
    feed_generator.logo(logo_url)
    feed_generator.link(href=f'{podcast_path}/{RSS_FILE}', rel='self')
    feed_generator.language('en')
    feed_generator.pubDate(publication_date)
    feed_generator.lastBuildDate(publication_date)

    feed_generator.podcast.itunes_category('Arts')
    feed_generator.podcast.itunes_category('Comedy')
    feed_generator.podcast.itunes_category('Music')
    feed_generator.podcast.itunes_category('News')
    feed_generator.podcast.itunes_category('Sports')
    feed_generator.podcast.itunes_author('BBC Sounds')
    feed_generator.podcast.itunes_block(True)
    feed_generator.podcast.itunes_explicit('no')
    feed_generator.podcast.itunes_image(logo_url)
    feed_generator.podcast.itunes_owner(name='BBC', email='RadioMusic.Support@bbc.co.uk')

    for episode in episodes:
        audio_url = f'{podcast_path}/{episode.output_filename}'
        image_url = f'{podcast_path}/{episode.image_filename}'

        feed_entry = feed_generator.add_entry()
        feed_entry.id(audio_url)
        feed_entry.title(episode.title)
        feed_entry.description(episode.description)
        feed_entry.enclosure(url=audio_url, length=str(episode.size_in_bytes()), type='audio/mpeg')
        feed_entry.published(episode.published())
        feed_entry.link(href=episode.url)
        feed_entry.podcast.itunes_duration(episode.duration_in_seconds())
        feed_entry.podcast.itunes_image(image_url)
        feed_entry.podcast.itunes_author('BBC Sounds')

    feed_generator.rss_file(RSS_FILE, pretty=True)
