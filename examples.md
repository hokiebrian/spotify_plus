## Examples of what can be done

* [Custom Button Card](https://github.com/custom-cards/button-card) is the most commonly used card below
* [Auto Entities](https://github.com/thomasloven/lovelace-auto-entities) is also used for the repetitive displays, like Artists, Albums, Tracks, etc.
* [Markdown Card](https://www.home-assistant.io/dashboards/markdown/) Markdown card is used for the table displays of data, using for loops.
* [Home Assistant Helpers](https://www.home-assistant.io/integrations/#helper) Helpers are used for the parameter selections and sync with current track info
* [Expander Card](https://github.com/Alia5/lovelace-expander-card) Expander Card is used to keep everything tidy

I'm not providing any lovelace at this time as I leverage a lot of templates, and they can be modernized:

[Reusable Templates in Home Assistant was recently introduced](https://www.home-assistant.io/docs/configuration/templating/#reusing-templates) 

***
### Music Machine:
Use the Services Tab to select which song features you want to use to narrow your generated set of songs. 

<img src="/images/music_machine.png" width=40%>

Using helpers in an entities card for all the variables in the `spotify_plus.spotify_music_machine` service. 

Across the top in a sync function that changes all of the helper values to that of the current song and puts "Similar to: CURRENT_SONG" in the name field. 

Then generate a song list based on the song value parameters of the current track using a button press that calls the `spotify_plus.spotify_music_machine` service.

There are also preset icons that call `scene.turn_on` of a scene that is defined with preset values for all the helpers.

<img src="/images/music_machine.jpg" width=30%>

See the data that went into your generated list of music (data from `sensor.spotify_music_machine`):

<img src="/images/music_machine_metadata.jpg" width=40%>

***
### Search:
Perform a search from the Services tab (data from `sensor.spotify_search`)

<img src="/images/search_service.png" width=40%>

Search Results:

Show related artists from Artist Profile search. In this card, there is a `tap_action` to trigger the Artist Profile search for the selected Artist.

A `double_tap_action` follows the artist.

There is a floating spotify icon that is a solid green is the item is followed. 

<img src="/images/search_artist_profile_related.jpg" width=30%>

Same as above but for the Artist's Top Tracks

<img src="/images/search_artist_top_tracks_follow.jpg" width=30%>

***
### Show My playlists (data from `sensor.spotify_playlist_info`):

<img src="/images/my_playlists.jpg" width=40%>

***
### Playlist Analysis (data from `sensor.spotify_playlist_info`):

<img src="/images/playlist_analysis.jpg" width=40%>

***
### Artist Frequency Analysis (data from `sensor.spotify_analysis`):

<img src="/images/history_playlist_analysis.jpg" width=40%>

***
### Player Card (data from `sensor.spotify_song_details`):

Highlight followed items with green circle. 

Use the Color Extractor Integration to trigger Hue lights to change to album cover primary color.

<img src="/images/player_w_playlist_followed.jpg" width=40%>

***
### Queue and Recent Items (data from `sensor.spotify_extras`):

Followed items have solid green Spotify icon

<img src="/images/queue.jpg" width=40%>

<img src="/images/recently_played.jpg" width=40%>

***
### Spotify Profile Card (data from `sensor.spotify_plus`):

Also add a listening history graph using a history_stats sensor.

<img src="/images/profile_card.jpg" width=40%>

***
