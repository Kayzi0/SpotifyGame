import streamlit as st
import pandas as pd
import hashlib
import random

# -----------------------
# App setup
# -----------------------
st.set_page_config(page_title="Spotify Music Game", layout="centered")
st.title("🎶 Spotify Music Game")

# -----------------------
# Initialize session state
# -----------------------
if "game_playlist" not in st.session_state:
    st.session_state.game_playlist = None

if "current_index" not in st.session_state:
    st.session_state.current_index = 0

if "scores" not in st.session_state:
    st.session_state.scores = {}

if "current_song" not in st.session_state:
    st.session_state.current_song = None

if "player_order" not in st.session_state:
    st.session_state.player_order = []

if "current_turn" not in st.session_state:
    st.session_state.current_turn = 0

if "songs_per_player" not in st.session_state:
    st.session_state.songs_per_player = 10

if "uploaded_playlists" not in st.session_state:
    st.session_state.uploaded_playlists = pd.DataFrame()

if "playlist_hashes" not in st.session_state:
    st.session_state.playlist_hashes = set()

if "previous_song_year" not in st.session_state:
    st.session_state.previous_song_year = None

if "current_song_year" not in st.session_state:
    st.session_state.current_song_year = None

if "game_finished" not in st.session_state:
    st.session_state.game_finished = False

# -----------------------
# Tabs
# -----------------------
tab1, tab2 = st.tabs(["🎮 Game", "📁 Upload Playlists"])

# -----------------------
# TAB 2: Upload Playlists
# -----------------------
with tab2:
    st.header("📁 Upload Playlists")
    st.write("Upload Spotify playlist CSV files exported from Spotify.")
    st.info(
        "💡 **How to export your playlists:** Visit [Exportify](https://exportify.net/) to download your Spotify playlists as CSV files."
    )

    with st.form("upload_form"):
        uploaded_file = st.file_uploader("Choose a CSV file", type="csv")
        user_name = st.text_input("User name", placeholder="e.g., Emily")
        playlist_year = st.number_input(
            "Playlist year", min_value=2000, max_value=2030, value=2024, step=1
        )
        submit_upload = st.form_submit_button("Upload Playlist")

        if submit_upload and uploaded_file and user_name:
            try:
                # Read the uploaded CSV
                df_upload = pd.read_csv(uploaded_file)

                # Create a hash of the file content to detect duplicates
                file_content = uploaded_file.getvalue()
                file_hash = hashlib.md5(file_content).hexdigest()

                if file_hash in st.session_state.playlist_hashes:
                    st.warning(f"⚠️ This playlist has already been uploaded!")
                else:
                    # Add User and playlist year columns
                    df_upload["User"] = user_name
                    df_upload["playlist year"] = playlist_year

                    # Extract release year from Release Date if it exists
                    if "Release Date" in df_upload.columns:
                        release_dt = pd.to_datetime(
                            df_upload["Release Date"], errors="coerce", format="mixed"
                        )
                        df_upload["release_year"] = release_dt.dt.year.astype("Int64")

                    # Keep only necessary columns (if they exist)
                    columns_to_keep = [
                        "Track URI",
                        "Track Name",
                        "Artist Name(s)",
                        "Duration (ms)",
                        "Popularity",
                        "Explicit",
                        "User",
                        "playlist year",
                        "release_year",
                    ]
                    available_columns = [
                        col for col in columns_to_keep if col in df_upload.columns
                    ]
                    df_upload = df_upload[available_columns]

                    # Append to uploaded playlists
                    if st.session_state.uploaded_playlists.empty:
                        st.session_state.uploaded_playlists = df_upload
                    else:
                        st.session_state.uploaded_playlists = pd.concat(
                            [st.session_state.uploaded_playlists, df_upload],
                            ignore_index=True,
                        )

                    # Store hash
                    st.session_state.playlist_hashes.add(file_hash)

                    st.success(
                        f"✅ Uploaded {len(df_upload)} songs from {user_name} ({playlist_year})"
                    )

            except Exception as e:
                st.error(f"❌ Error uploading file: {e}")
        elif submit_upload:
            st.warning("Please select a file and enter a user name.")

    # Display overview of uploaded playlists
    st.divider()
    st.subheader("📊 Uploaded Playlists Overview")

    if not st.session_state.uploaded_playlists.empty:
        # Group by User and playlist year
        overview = (
            st.session_state.uploaded_playlists.groupby(["User", "playlist year"])
            .size()
            .reset_index(name="Number of Songs")
        )
        st.dataframe(overview, width="stretch")

        # Summary stats
        total_songs = len(st.session_state.uploaded_playlists)
        total_users = st.session_state.uploaded_playlists["User"].nunique()
        st.info(f"📈 Total: {total_songs} songs from {total_users} user(s)")

        # Option to clear all uploads
        if st.button("🗑️ Clear All Uploads"):
            st.session_state.uploaded_playlists = pd.DataFrame()
            st.session_state.playlist_hashes = set()
            st.rerun()
    else:
        st.info("No playlists uploaded yet. Upload your first playlist above!")

# -----------------------
# TAB 1: Game
# -----------------------
with tab1:
    # -----------------------
    # Load data
    # -----------------------
    @st.cache_data
    def load_default_data():
        try:
            return pd.read_csv("filtered_list.csv")
        except FileNotFoundError:
            return pd.DataFrame()

    # Use uploaded playlists if available, otherwise use default
    if not st.session_state.uploaded_playlists.empty:
        df = st.session_state.uploaded_playlists.copy()
    else:
        df = load_default_data()
        if df.empty:
            st.warning(
                "⚠️ No playlists loaded. Please upload playlists in the 'Upload Playlists' tab."
            )
            st.stop()

    # -----------------------
    # Helper functions
    # -----------------------
    def start_game():
        songs_per_user = st.session_state.songs_per_player

        selected = (
            df.groupby("User", group_keys=False)
            .apply(
                lambda group: group.sample(n=min(songs_per_user, len(group))),
                include_groups=False,
            )
            .reset_index(drop=True)
        )

        playlist = selected.sample(frac=1).reset_index(drop=True)

        st.session_state.game_playlist = playlist
        st.session_state.current_index = 0
        st.session_state.game_finished = False

        # Set initial random year for the first song based on collection range
        if "release_year" in df.columns:
            valid_years = df["release_year"].dropna()
            if len(valid_years) > 0:
                min_year = int(valid_years.min())
                max_year = int(valid_years.max())
                st.session_state.previous_song_year = random.randint(min_year, max_year)
            else:
                st.session_state.previous_song_year = None
        else:
            st.session_state.previous_song_year = None

        st.success("🎮 Game started! Click 'Play Next Song'")

    def play_next_song():
        idx = st.session_state.current_index
        playlist = st.session_state.game_playlist

        if idx >= len(playlist):
            return

        row = playlist.iloc[idx]

        track_name = row["Track Name"]
        artist = row["Artist Name(s)"]
        track_uri = row["Track URI"]
        release_year = row.get("release_year", "Unknown")

        matches = df[
            (df["Track Name"] == track_name) & (df["Artist Name(s)"] == artist)
        ]

        # BEFORE overwriting, shift current -> previous
        if st.session_state.current_song_year is not None:
            st.session_state.previous_song_year = st.session_state.current_song_year

        # Update current song year (for NEXT time)
        if release_year != "Unknown":
            st.session_state.current_song_year = release_year
        else:
            st.session_state.current_song_year = None

        # Store the current song info
        st.session_state.current_song = {
            "index": idx + 1,
            "total": len(playlist),
            "track": track_name,
            "artist": artist,
            "release_year": release_year,
            "playlist_years": sorted(
                matches["playlist year"].dropna().unique().tolist()
            ),
            "users": sorted(matches["User"].unique().tolist()),
            "uri": track_uri,
        }

        st.session_state.current_index += 1

        num_players = len(st.session_state.player_order)
        if num_players > 0:
            st.session_state.current_turn = (
                st.session_state.current_turn + 1
            ) % num_players

    def update_score(player, points):
        st.session_state.scores[player] += points

    def finish_game():
        """Mark the game as finished after the last song has been scored"""
        st.session_state.game_finished = True

    def restart_game():
        st.session_state.game_playlist = None
        st.session_state.current_index = 0
        st.session_state.current_song = None
        st.session_state.scores = {}
        st.session_state.player_order = []
        st.session_state.current_turn = 0
        st.session_state.previous_song_year = None
        st.session_state.current_song_year = None
        st.session_state.game_finished = False

    # -----------------------
    # Display current song
    # -----------------------
    if st.session_state.current_song and not st.session_state.game_finished:
        song = st.session_state.current_song

        st.subheader(f"🎵 Song {song['index']} / {song['total']}")

        # Display whose turn it is alongside the song
        if st.session_state.player_order:
            current_player = st.session_state.player_order[
                st.session_state.current_turn
            ]
            st.info(f"🎯 **It's {current_player}'s turn!**")

        # Display previous song's release year
        if st.session_state.previous_song_year is not None:
            st.write(
                f"🕒 **Previous song was released in:** {st.session_state.previous_song_year}"
            )

        st.write(f"**Track:** {song['track']}")
        st.write(f"**Artist:** {song['artist']}")
        st.write(f"**Release year:** {song['release_year']}")
        st.write(f"**Playlist year(s):** {song['playlist_years']}")
        st.write(f"**Appears in playlists of:** {song['users']}")

        # Add clickable link to play full song on Spotify
        st.link_button("🎵 Play on Spotify", song["uri"], width="stretch")

    # -----------------------
    # Game controls
    # -----------------------
    st.divider()

    def show_pause_reminder():
        if st.session_state.current_index > 0:
            st.warning("⏸️ Please pause the previous song before playing the next one")

    if st.session_state.game_playlist is None:
        st.subheader("⚙️ Game Settings")
        songs_per_player = st.number_input(
            "Songs per player",
            min_value=1,
            max_value=50,
            value=st.session_state.songs_per_player,
            step=1,
            help="Number of songs to select from each user's playlists",
        )
        st.session_state.songs_per_player = songs_per_player

        st.button("🎮 Start Game", on_click=start_game)

    elif st.session_state.game_finished:
        # Game is completely over - show winner and restart option
        st.success("🎉 **Game Over!**")

        # Display winner(s)
        if st.session_state.scores:
            max_score = max(st.session_state.scores.values())
            winners = [
                player
                for player, score in st.session_state.scores.items()
                if score == max_score
            ]

            if len(winners) == 1:
                st.subheader(f"👑 Winner: {winners[0]} with {max_score} points!")
            else:
                st.subheader(
                    f"👑 It's a tie! Winners: {', '.join(winners)} with {max_score} points!"
                )
        else:
            st.info("No scores recorded.")

        st.button("🔄 Restart Game", on_click=restart_game)

    else:
        # Game is in progress
        all_songs_played = st.session_state.current_index >= len(
            st.session_state.game_playlist
        )

        if all_songs_played:
            # All songs have been played, but allow scoring the last one
            st.info(
                "🎵 That was the last song! Score it below, then click 'Finish Game' to see the winner."
            )
            st.button("🏁 Finish Game", on_click=finish_game, width="stretch")
        else:
            # More songs to play
            show_pause_reminder()
            st.button("▶️ Play Next Song", on_click=play_next_song, width="stretch")

            # Show who will play AFTER the next click
            if st.session_state.player_order:
                num_players = len(st.session_state.player_order)
                next_turn = (st.session_state.current_turn + 1) % num_players
                next_player = st.session_state.player_order[next_turn]
                st.caption(f"🔜 Next up: {next_player}")

    # -----------------------
    # Scoreboard
    # -----------------------
    st.divider()
    st.header("🏆 Scoreboard")

    # Add player (only before game starts)
    if st.session_state.game_playlist is None:
        st.subheader("👥 Players")

        with st.form("add_player"):
            new_player = st.text_input("Add player")
            submitted = st.form_submit_button("Add")

            if submitted and new_player:
                if new_player not in st.session_state.scores:
                    st.session_state.scores[new_player] = 0
                    st.session_state.player_order.append(new_player)

    else:
        st.info("🔒 Players are locked for this game.")

    # Add points (available during game and after last song, but not after "Finish Game")
    if st.session_state.scores and not st.session_state.game_finished:
        player = st.selectbox("Player", list(st.session_state.scores.keys()))
        points = st.number_input("Points", step=1, value=1)

        if st.button("➕ Add Points"):
            update_score(player, points)

    # Display leaderboard
    if st.session_state.scores:
        score_df = pd.DataFrame.from_dict(
            st.session_state.scores, orient="index", columns=["Score"]
        ).sort_values("Score", ascending=False)

        st.table(score_df)
    else:
        st.info("No players yet.")
