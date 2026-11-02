"""Silver native trial, using the verified isolated font/advance patch pipeline."""
from contextlib import contextmanager
import native_m6x11 as engine

OUT=engine.ROOT/'build/reusable-atlas-noto-ui-r35-native-silver-v1'
FACE=engine.trial.OUT/'fonts/Silver.ttf'


@contextmanager
def configured():
    options=dict(OUT=OUT,FACE=FACE,EM=19,FONT_ID='silver',
                 FONT_NAME='Silver by Poppy Works / Wolfgang Wozniak',
                 FALLBACK='',FALLBACK_INDICES=set())
    previous={key:getattr(engine,key) for key in options}
    try:
        for key,value in options.items():setattr(engine,key,value)
        yield engine
    finally:
        for key,value in previous.items():setattr(engine,key,value)


if __name__=='__main__':
    with configured() as builder:builder.build()
