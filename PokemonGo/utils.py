from difflib import SequenceMatcher


SIMILARITY_MIN = 0.9


def are_similar(x: str, y: str) -> bool:
    '''
    Determine if string similarity is above a threshold.
    WARNING: For short strings, user may want to decrease SIMILARITY_MIN.
    '''

    likeness = SequenceMatcher(None, x, y).ratio()

    if likeness >= SIMILARITY_MIN:
        prompt = 'Found similar match \'{}\'. Accept? (y/n)\t'.format(x)
        if input(prompt) == 'y':
            return True
        else:
            return False

    return False