function schematron(input, schematronCode, resultsSelect) {

    resultsSelect.length = 0;

    setDocument(resultEditor,`Starting Schematron validation ...`,'text');

    writeResult(window.frames['current-result-frame'], '');

    var transformationResult, responseData;

    fetch(baseURI + 'schematron',
        {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                inputCode: schematronCode,
                inputData: input,
                inputType: 0
            })
        })
        .then(response => response.json()
            .then(json => {
                if (json.results == null) {
                    resultsSelect.length = 0;
                    setDocument(
                        resultEditor,
                        `Error(s) during Schematron evaluation: ${json.messages}`,
                        'text');
                } else {
                    resultsSelect.length = 0;


                    json.results.forEach((result, index) => {
                        resultsSelect.appendChild(new Option(`result ${index}`, result));
                        if (index === 0) {
                            writeResult(window.frames['current-result-frame'], result);
                        }
                    });

                    resultsSelect.onchange = function (evt) {
                        //var selectedResult = responseData.ResultDocuments[this.selectedIndex];
                        setDocument(resultEditor, resultsSelect.value, 'xml');

                        if (document.getElementById('render-box').checked) {
                            writeResult(window.frames['current-result-frame'], resultsSelect.value);
                        }
                    };

                    setDocument(resultEditor, json.results[0], 'xml');
                }
            }));
}