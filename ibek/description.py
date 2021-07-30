from apischema import schema


def desc(description: str):
    return schema(description=description)
