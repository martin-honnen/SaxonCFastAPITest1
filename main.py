from contextlib import asynccontextmanager

from fastapi import FastAPI

from saxonche import PySaxonProcessor, PySaxonApiError

# create single Saxon processor
saxon_proc = PySaxonProcessor()
saxon_proc.set_configuration_property('http://saxon.sf.net/feature/allowedProtocols', 'http,https')



@asynccontextmanager
async def lifespan(app: FastAPI):
    # use single Saxon processor
    #
    yield
    # clean up Saxon processor
    #if saxon_proc is not None:
    #    saxon_proc.detach_current_thread


app = FastAPI(lifespan=lifespan)


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/hello/{name}")
async def say_hello(name: str):
    try:
        xdm_doc = saxon_proc.parse_xml(xml_file_name=name)
        xpath_proc = saxon_proc.new_xpath_processor()
        xpath_proc.set_context(xdm_item=xdm_doc)
        xpath_result = xpath_proc.evaluate('root/foo ! map { local-name() : string() }')
        api_result = [{key.string_value : map.get(key).head.string_value} for map in xpath_result for key in map.keys() ]
        return api_result
    except PySaxonApiError as e:
        return {"error": str(e)}
