## Spotify Plus Tools

![release_badge](https://img.shields.io/github/v/release/hokiebrian/spotify_plus?style=for-the-badge)
![release_date](https://img.shields.io/github/release-date/hokiebrian/spotify_plus?style=for-the-badge)
[![License](https://img.shields.io/github/license/hokiebrian/spotify_plus?style=for-the-badge)](https://opensource.org/licenses/Apache-2.0)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge)](https://github.com/custom-components/hacs)

### **Installation**

**Pre-requisites:**
- A **Premium** Spotify Subscription
- Follow the Home Assistant Spotify instructions (https://www.home-assistant.io/integrations/spotify/) to get your Key and Secret

**Optional pre-requisites:**
- A MusixMatch API Key (free)
- Your playlist ID for Spotify that you'd like to add your listening history to (just the ID, not the full URI)
***
1) Make sure that [Home Assistant Community Store (HACS)](https://github.com/custom-components/hacs) is setup.
2) Go to integrations in HACS
3) Click the 3 dots in the top right corner and choose `Custom repositories`
4) Paste the following into the repository input field `https://github.com/hokiebrian/spotify_plus` and choose category of `Integration`
5) Click add and restart HA to let the integration load
6) Go to settings and choose `Devices & Services`
7) Click `Add Integration` and search for `Spotify Plus`
8) Follow the instructions for Home Assistant Spotify (https://www.home-assistant.io/integrations/spotify/) to connect your Spotify account
9) Optionally add your MusixMatch API key and Spotify History Playlist
10) Restart Home Assistant

If the optional data is left blank, those features will not be called upon. You can simply enable those features by putting valid keys in the space provided.
***

### **Overview**

This provides an enhanced experience for Spotify in your Home Assistant instance.

### Who is this for?
This platform is for Home Assistant users that want to leverage Home Assistant to be deeply integrated with their Spotify listening. Out of the box, it is a Spotify Media Player. What you do with it beyond that is entirely up to you. A tremendous amount of Spotify data is accessible through these services and some fun and exciting cards, automations, scripts and interfaces can be built on top of this data. 

### What is does?
- Provides a playlist and queue creation utility that is highly customizable
- Provides a simple Media Player entity that updates every 3 seconds
- Provides various services to deeply interact with your Spotify Account
- A handy search feature that can perform Artist Profile lookups as well as a normal search
- Provides direct links to your Top Artist and Followed Artists Radio Stations and Playlists
- Analyzes your playlists (up to 100 tracks) for Spotify song parameters (e.g. Energy, Valence, etc.)
- Pull your queue and recent items

Optional Functions:
- Provides link to external Lyrics provider (MusixMatch)
- Add tracks to a spotify playlist of your choosing


Usage:
- All of the services are available to be called from the Home Assistant Frontend or via Automations and Scripts
- As a suggestion, add an automation that triggers when the Player attribute `media_content_id` changes and call the `get_song_data` and `extras` services
- Set your artists and playlists to refresh at whatever interval you choose. They do not poll at all unless called upon, but the data will survive restarts. 
- Use auto-entities or Markdown cards to generate cards for your artists, playlists, search results, queue, recent items, etc. (Examples to be provided at a future date)
- Use Song Info to visualize current track parameters (Energy, Valence, etc.)
- See [examples.md](/examples.md) for interface examples

### Stand-alone Sensors:
#### `sensor.spotify_plus` - This reflects your User Profile with Spotify. It will provide your profile name, image, the number of artists, albums and track you follow/like and your available listening devices.

### Media Player:
#### `media_player.spotify_ACCTNAME` - Standard media player entity, with some additional attributes. The additional attributes do not require any additional API calls.

***
### Services (and how to use them):

### Service: `spotify_plus.spotify_music_machine`
This service does the fun stuff. Select values for a playlist or queue of songs. All settings are optional. The service will leverage a selected set of artists (either your Top Artists - up to the top 100 - or the collective of your followed artists. Top Artists time range can be selected (1m, 6m, 1y+). Based on that info, a random selection of 10 artists will be selected as seeds for your playlist / queue, along with the song feature parameters you select. You can dump the recommendations to a playlist or have the selection be ephemeral and just get dropped into your queue. You can play immediately, or just create a playlist to consume later. 

The track parameters you enter are passed to Spotify with a default range of +/- 20% around the entered values. If your value is 50%, the submitted ranged will be .30 - .70. The exceptions are hard pinned values for a few options, such as energy. If you pin energy to 100, the range will only br 90-100 instead of 80-100. If you simply drop it to 99, the range will be 79-100. This helps to get you a set of songs that really meet your needs if you want to go extreme on a setting. 

If the pre-filtered recommended track list is small (<50), the service will perform an additional query for tracks based on your Top 50 tracks in an effort to boost the playlist size. 

The best way to consume this service is to try it out. It is very responsive and you'll get a 100 track playlist very quickly. 

#### TIP: Use an automation to create playlists for you daily. This is somewhat similar to the Daily Mix playlists Spotify does for you already, but these will provide a bit more randomness.
#### TIP: Use the services tab to test it all out, have fun with it, experiment. If you are too extreme on values, your playlist size may be very small. 
#### TIP: Use scenes to preset the values of Valence, Energy, etc. and provide one-click create and play of predefined parameters. "I want some peaceful music now" - one click, music plays. 
#### TIP: Create input_number helpers to align with the service parameters. Use a script to sync the current values from a playing track. 
#### TIP: Use the optional parameter in the service 'Recommendation Tolerance' to tweak the breadth of the parameters. The default is +/- 20%. Making this much smaller than that will limit the number of tracks returned.

#### Sensor: `sensor.spotify_music_machine` - this sensor and the attributes capture the parameters used in the recommendations query and the results. 

***
### Service: `spotify_plus.get_song_data`
This service does a deep dive on the current track. Track name, album, album track number, track length, track audio features, boolean if you are following the arist/album/track, ISRC, link to MusixMatch Lyric (if you provided an API key), and more. 

#### Sensor: `sensor.spotify_song_details` - Attributes contain all of the detailed information from above
#### TIP: Use an automation to trigger whenever the 'media_content_id' attribute changes on the media_player to call this service along with the `spotify_plus.spotify_extras` service.

#### Additional Services Related to Song Data:
These services will add the item to your library:
* `spotify_plus.spotify_manage_artist`
* `spotify_plus.spotify_manage_album`
* `spotify_plus.spotify_manage_track`
* `spotify_plus.spotify_manage_playlist`
#### TIP: Use this service as a tap_action for any visulized artist/album/track/playlist to one-click add to your library

All of these services can accept the ID/URI for the artist/album/track/playlist as an optional argument. If no data is passed, it will assume the current artist/album/track/playlist that is currently playing

***
### Service: `spotify_plus.spotify_extras`
Extras pulls the current queue and recently played items, along with all the attributes of the tracks. 
#### TIP: Use the list of recent items to go back and add them to your library 
#### Sensor: sensor.spotify_extras - two attributes, queue and recent, contain the tracks of each

***
### Service: `spotify_plus.spotify_add_to_history`
This service adds the currently playing track to the playlist ID you configured in the integration options. It will check if the item exists in the history playlist, remove it and re-add it to the top of the playlist. The goal here is to capture all of the unique tracks listened to. 

#### TIP: Use in an automation, if a track has been playing for XX seconds, call the service. This prevents skipped tracks from being added
#### Sensor: `sensor.spotify_add_to_history_playlist` - simply shows which track name was added. Attributes capture time added, the playlist image and total number of tracks in the playlist

***
### Service: `spotify_plus.spotify_analysis`
This service takes the history playlist referenced above and analyzes the frequency of artists then sorts the list by frequency. That's it.
#### TIP: 
#### Sensor: `sensor.spotify_analysis`

***
### Service: `spotify_plus.spotify_my_artists`
This service gathers data (Name, Image, Spotify URI) for all of your followed artists, along with their key playlists, such as "ARTIST Radio" and "This is ARTIST". 
#### Sensor: `sensor.spotify_my_artists` - attribute 'my_artists' contains all of the artist details, arranged alphabetically.

***
### Service: `spotify_plus.spotify_top_artists`
This service gathers data (Name, Image, Spotify URI) for your top 99 artists, along with their key playlists, such as "ARTIST Radio" and "This is ARTIST". 
#### Sensor: `sensor.spotify_top_artists` - attribute 'top_artists' contains all of the artist details, arranged alphabetically.

***
### Service: `spotify_plus.spotify_playlist_info`
This service gathers data (Name, Image, Spotify URI, Average of Song Features (energy, valence, etc.), number of tracks) for all of your created or followed playlists. 
#### NOTE: This only analyzes the first 100 tracks of a playlist, which should provide an adequate sample of the playlist song features
#### TIP: Use Playlist Song Feature data to filter your playlists based on a feature like 'energy'
#### TIP: Call `media_player.play_media` with the spotify URI provided to quickly play your desired playlist.
#### Sensor: `sensor.spotify_playlist_info` - attribute 'playlists' contains all of the playlist details, arranged alphabetically with the "Daily Mix" playlists on top if you are following your Spotify-curated Daily Mix playlists

***
### Service: `spotify_plus.spotify_search`
Search Spotify... with a twist! There are two search methods, `Artist Profile` and `General Search`. Artist Profile will provide Artist details, such as albums (listed reverse chronologically), top tracks, playlists and Related Artists. The General Search is just that, with results broken into tracks, albums, playlists.
#### TIP: Use automations to automatically perform a search of the current artist to get real-time profile data of the currently playing artist
#### TIP: Use URI from search results to perform actions, such as play_media, trigger a refreshed search (in the case of related artists) or even launch spotify with context using a url action.
#### Sensor: `sensor.spotify_search` - shows most recent search term, attributes contain search results and search orgin type.

***
## Troubleshooting:
* What's up with these recorder errors saying the attribute fields are too large? It is recommended to exclude an entity_glob from the recorder (exclude sensor.spotify_*). The secondary sensors that have large amounts of attribute data will survive a reboot, even if they are excluded from the recorder.
* I get "No Active Device" errors and nothing plays? This is a Spotify limitation. If the backend player has a state of Idle, you cannot pass a play command without passing a device_id along with it. Keep this in mind when calling services that use the service to trigger play events. The other option is to simply call media_player.select_source and activate the player. You'll see the status of the player go from 'idle' to 'paused'. You can always check this in your script or automation conditions.
* My playlists have almost no tracks - your parameters are too off balance, play with the values.
* Where is Tempo? Why can't I enter that? Tempo is a highly deceptive metric assigned by Spotify. It is all but guaranteed you'll be frustrated. I tried many different ways to make this work, but the metric just isn't a reliable one. I'd recommend using some other parameters, such as Dancability, to tweak your tracks.
***
## Other Info:
* The Spotify API is typically very responsive and has few issues. There is always the random disconnect and other odd behaviors. This platform hits the API every 3 seconds with a light request and has proven reliable at that frequency. It was tested with a 1 second update interval and it worked great - but 86,400 requests per day seemed excessive, so it's 28,800.
