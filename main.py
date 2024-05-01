from contextlib import asynccontextmanager

from fastapi import FastAPI

from fastapi.staticfiles import StaticFiles

from pydantic import BaseModel

from enum import Enum

from starlette.responses import FileResponse


class InputType(str, Enum):
    XML = "xml"
    JSON = "json"
    TEXT = "text"
    NONE = "None"
class CodeType(str, Enum):
    XSLT = 0,
    XQuery = 1,
    XPath = 2,
    Schematron = 3
class Request(BaseModel):
    inputCode:str
    #codeType:str
    inputData:str | None = None
    inputType:str | int

from saxonche import PySaxonProcessor, PySaxonApiError, PyXdmFunctionItem

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

app.mount("/static", StaticFiles(directory="static"), name="static")
@app.get("/")
async def root():
    return FileResponse("static/index.html")


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


@app.post("/api/xquery")
async def xquery(xquery_request: Request):
    input_type = xquery_request.inputType
    xquery_code = xquery_request.inputCode

    xquery_processor = saxon_proc.new_xquery_processor()

    try:
        xquery_processor.set_query_content(xquery_code)
    except RuntimeError as e:
        return {'messages': str(e)}
    else:
        input_data = xquery_request.inputData
        if input_type == 0 and input_data is not None:
            try:
                xdm_input = saxon_proc.parse_xml(xml_text=input_data, encoding="utf8")
            except RuntimeError as e:
                return {'messages': f'Error parsing your XML input: {e}'}
            else:
                xquery_processor.set_context(xdm_item=xdm_input)
        elif input_type == 1 and input_data is not None:
            try:
                json_input = PyXdmFunctionItem().get_system_function(saxon_proc, '{http://www.w3.org/2005/xpath-functions}parse-json', 1).call(saxon_proc, [saxon_proc.make_string_value(input_data, encoding="utf8")])
            except RuntimeError as e:
                return {'messages': f'Error parsing your JSON input: {e}'}
            else:
                xquery_processor.set_context(xdm_item=json_input.head)
        elif input_type == 2 and input_data is not None:
            xquery_processor.set_context(xdm_item=saxon_proc.make_string_value(input_data, encoding="UTF-8"))

        try:
            serialized_result = xquery_processor.run_query_to_string()
        except RuntimeError as e:
            result_python_map = {'messages': f'{e}', 'results': None}
        else:
            result_python_map = { 'results': [serialized_result] }

        xquery_processor.exception_clear()

        return result_python_map