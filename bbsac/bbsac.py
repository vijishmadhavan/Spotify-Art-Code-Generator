from colorthief import ColorThief
from PIL import Image
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from spotipy.oauth2 import SpotifyOAuth
import tqdm

import argparse
import io
import os
import re
from urllib.request import urlopen


def rgb_to_hex(rgb):
    """Converts rgb value to hex.

    :param rgb: rgb value
    :returns: hex value of input
    """
    return "%02x%02x%02x" % rgb


def get_art_with_code(uri: str, sp: spotipy.Spotify):
    """ Generates Spotify Art + Code for a given URI.

    :param uri: Spotify URI
    :param sp: a spotipy instance
    :returns: album / track / artist art with Spotify Code 
    """
    if re.match(r"spotify:track:[A-Za-z0-9]{22}", uri):
        test = sp.track(uri)
        cover_uri = test["album"]["uri"]
        results = sp.album(cover_uri)

    elif re.match(r"spotify:artist:[A-Za-z0-9]{22}", uri):
        results = sp.artist(uri)

    elif re.match(r"spotify:album:[A-Za-z0-9]{22}", uri):
        results = sp.album(uri)
    else:
        return None

    link_to_cover = results["images"][0]["url"]
    cover_size = results["images"][0]["height"]
    cover_image = Image.open(urlopen(link_to_cover))

    # get dominant color from cover
    # this doesnt write to disc and still allows colorthief to grab most dominant color
    with io.BytesIO() as file_object:
        cover_image.save(file_object, "PNG")
        cf = ColorThief(file_object)
        dominant_color_rgb = cf.get_color(quality=1)

    dominant_color_hex = rgb_to_hex(dominant_color_rgb)
    code_color = (
        "black"
        if (dominant_color_rgb[0] + dominant_color_rgb[1] + dominant_color_rgb[2])
        / 3
        > 127
        else "white"
    )
    uri_call = uri.replace(":", "%3A")

    # get spotify code
    url = (
        "https://www.spotifycodes.com/downloadCode.php?uri=png%2F"
        + f"{dominant_color_hex}%2F{code_color}%2F{cover_size}%2F{uri_call}"
    )
    album_code = Image.open(urlopen(url))

    # merge images
    final_height = album_code.size[1] + cover_size
    im = Image.new(mode="RGB", size=(cover_size, final_height))
    im.paste(cover_image, (0, 0))
    im.paste(album_code, (0, cover_size))
    return im


def save_art_with_code(output_folder: str, uris: list[str], sp: spotipy.Spotify):
    """Generates and saves Spotify Art + Code for all URIs to output_folder.

    :param output_folder: path where results will be saved to
    :param album_uris: list of spotify URIs
    :param sp: spotipy instance
    """
    for uri in tqdm.tqdm(uris, desc="generating album codes "):
        im = get_art_with_code(uri, sp)
        filename = uri.replace(":", "-")
        im.save(f"{output_folder}/{filename}.png")

def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-o", dest="out", type=str, required=False, help="path to output folder"
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--u",
        dest="uris",
        nargs=1,
        type=str,
        help="comma separated Spotify URI(s)",
    )

    group.add_argument(
        "--a",
        dest="all_albums",
        action="store_true",
        required=False,
        help="flag for fetching all albums in your music library")

    args = parser.parse_args()

    # add current folder as fallback output folder
    if args.out is None:
        output_folder = os.path.dirname(os.path.realpath(__file__))
    else:
        output_folder = args.out

    if os.path.isdir(output_folder) is False:
        exit("supplied path is not a folder")

    if args.all_albums is False:
        if not (args.uris[0] and args.uris[0].strip()):
            exit("uris are blank")
        else:
            uri_list = args.uris[0].split(",")

        # SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET need to be exported first
        sp = spotipy.Spotify(
            client_credentials_manager=SpotifyClientCredentials())

    else:
        scope = "user-library-read"
        sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
            scope=scope, redirect_uri="http://127.0.0.1:9090"))

        # 50 item limit on getting saved albums, this adds the uris in chunks to uri_list
        items = True
        offset = 0
        uri_list = []
        while items:
            results = sp.current_user_saved_albums(limit=50, offset=offset)
            for album in results["items"]:
                uri_list.append(album["album"]["uri"])
            offset += 50
            if len(results["items"]) == 0:
                items = False

    save_art_with_code(output_folder, uri_list, sp)

if __name__ == "__main__":
    main()