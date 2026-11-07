"""Read gym badge screenshots: device profiles, preprocessing, OCR.

The pieces are independent. :mod:`~PokemonGo.vision.devices` knows where
things are on each phone, :mod:`~PokemonGo.vision.preprocess` prepares
image regions, :mod:`~PokemonGo.vision.engines` turns pixels into text,
and :mod:`~PokemonGo.vision.reader` combines them and chooses the best
reading.
"""
