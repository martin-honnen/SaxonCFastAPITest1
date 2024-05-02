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


@app.post("/api/transform")
async def transform(xslt_request: Request):

    input_type = xslt_request.inputType
    xslt_code = xslt_request.inputCode
    # works but doesn't provide error handling
    # fn_transform = PyXdmFunctionItem().get_system_function(saxon_proc, "{http://www.w3.org/2005/xpath-functions}transform", 1)
    # fn_transform_arg = saxon_proc.make_map2({'stylesheet-text': saxon_proc.make_string_value(xslt_code), 'delivery-format': saxon_proc.make_string_value('serialized'), 'base-output-uri': saxon_proc.make_string_value('http://example.com/string-results/')})
    # xdm_result = fn_transform.call(saxon_proc, [fn_transform_arg])
    xpath_processor = saxon_proc.new_xpath_processor()
    xpath_processor.set_parameter('stylesheet-text', saxon_proc.make_string_value(xslt_code, encoding="utf8"))

    input_data = xslt_request.inputData

    if input_type == 0 and input_data is not None:
        xpath_processor.set_parameter('source-text',
                                      saxon_proc.make_string_value(input_data, encoding="utf8"))
        fn_transform_call = "transform(map{'stylesheet-text':$stylesheet-text,'delivery-format':'serialized','source-node':parse-xml($source-text)})"
    elif input_type == 1 and input_data is not None:
        xpath_processor.set_parameter('json-text',
                                      saxon_proc.make_string_value(input_data, encoding="utf8"))
        fn_transform_call = "let $json-input := parse-json($json-text) return transform(map{'stylesheet-text':$stylesheet-text,'delivery-format':'serialized','global-context-item':$json-input,'initial-match-selection':$json-input})"
    elif input_type == 2 and input_data is not None:
        xpath_processor.set_parameter('input-text',
                                      saxon_proc.make_string_value(input_data, encoding="utf8"))
        fn_transform_call = "transform(map{'stylesheet-text':$stylesheet-text,'delivery-format':'serialized','global-context-item':$input-text,'initial-match-selection':$input-text})"

    else:
        fn_transform_call = "transform(map{'stylesheet-text':$stylesheet-text,'delivery-format':'serialized'})"

    try:
        xdm_map = xpath_processor.evaluate_single(fn_transform_call)
        # xdm_item = xpath_processor.evaluate_single(fn_transform_call)
    except RuntimeError as e:
        result_python_map = {'messages': f'{e}', 'results': None}
    else:
        # xdm_map = xdm_item.get_map_value()
        result_docs = []
        for uri in xdm_map.keys():
            result_docs.append({'url': uri.string_value, 'content': xdm_map.get(uri).head.string_value})
        result_python_map = {'results': result_docs}

    xpath_processor.exception_clear()

    return result_python_map

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

@app.post("/api/xpath")
async def xpath(xpath_request: Request):
    input_type = xpath_request.inputType
    xpath_code = xpath_request.inputCode

    xpath_processor = saxon_proc.new_xpath_processor()

    input_data = xpath_request.inputData

    if input_type == 0 and input_data is not None:
        try:
            xdm_input = saxon_proc.parse_xml(xml_text=input_data, encoding="utf8")
        except RuntimeError as e:
            return {'messages': f'Error parsing your XML input: {e}', 'results': None}
        else:
            xpath_processor.set_context(xdm_item=xdm_input)
    elif input_type == 1 and input_data is not None:
        try:
            json_input = PyXdmFunctionItem().get_system_function(saxon_proc, '{http://www.w3.org/2005/xpath-functions}parse-json', 1).call(saxon_proc, [saxon_proc.make_string_value(input_data, encoding="utf8")])
        except RuntimeError as e:
            return {'messages': f'Error parsing your JSON input: {e}', 'results': None}
        else:
            xpath_processor.set_context(xdm_item=json_input.head)
    elif (input_type == 2 and input_data is not None):
        xpath_processor.set_context(xdm_item=saxon_proc.make_string_value(input_data, encoding="UTF-8"))

    xpath_processor.set_property('!method', 'adaptive')
    xpath_processor.set_property('!indent', 'yes')

    try:
        xdm_result = xpath_processor.evaluate(xpath_code)
    except RuntimeError as e:
        result_python_map = {'messages': f'{e}', 'results': None}
    else:
        result_items = []
        for xdm_item in xdm_result:
            result_items.append(str(xdm_item))
        result_python_map = { 'results': result_items }

    xpath_processor.exception_clear()

    return result_python_map

@app.post("/api/schematron")
async def schematron(schematron_request: Request):
    schematron_code = schematron_request.inputCode
    xml_code = schematron_request.inputData

    #xslt30_processor = saxon_proc.new_xslt30_processor()

    #xslt30_processor.set_cwd('.')

    try:
        saxon_proc.clear_configuration_properties()
        xslt30_processor = saxon_proc.new_xslt30_processor()
        xslt30_processor.set_cwd('.')
        compiled_schxslt = xslt30_processor.compile_stylesheet(stylesheet_file='pipeline-for-svrl.xsl.SaxonEE12CompiledForHE.sef')
    except RuntimeError as e:
        return { 'messages' : f'Schematron compilation failed: {e}'}
    else:
        saxon_proc.set_configuration_property('http://saxon.sf.net/feature/allowedProtocols', 'http,https')
        xslt30_processor = saxon_proc.new_xslt30_processor()

        #doc_builder = saxon_proc.new_document_builder()

        try:
            schematron_node = saxon_proc.parse_xml(xml_text=schematron_code, encoding="utf8")#doc_builder.parse_xml(xml_text=schematron_code, encoding="utf8")
        except RuntimeError as e:
            return { 'messages' : f'Error(s) parsing your Schematron: {e}' }
        else:
            try:
                compiled_schematron = compiled_schxslt.apply_templates_returning_value(xdm_value=schematron_node)
            except RuntimeError as e:
                return { 'messages' : f'Schematron compilation failed: {e}' }
            else:
                xslt30_processor = saxon_proc.new_xslt30_processor()

                try:
                    compiled_schematron_executable = xslt30_processor.compile_stylesheet(stylesheet_node=compiled_schematron.head)
                except RuntimeError as e:
                    return { 'messages' : 'Schematron compilation failed: ' }
                else:
                    try:
                        xdm_node = saxon_proc.parse_xml(xml_text=xml_code, encoding="utf8")#doc_builder.parse_xml(xml_text=xml_code, encoding="utf8")
                    except RuntimeError as e:
                        return {'messages': f'Error(s) parsing input XML: {e}' }
                    else:
                        try:
                            validation_result = compiled_schematron_executable.transform_to_string(xdm_node=xdm_node)
                        except RuntimeError as e:
                            result_map = { 'messages' : f'Error(s) during Schematron validation: {e}'  }
                        else:
                            result_map = { 'results' : [ validation_result ] }

                        return result_map