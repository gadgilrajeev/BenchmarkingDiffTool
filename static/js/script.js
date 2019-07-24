function hideCommon(checkbox) {
    allRows = document.getElementsByTagName("tr")

    for(i = 0; i < allRows.length; i++)
    {
    	row = allRows[i].getElementsByTagName("td")
    	arr = []
    	for(j = 0; j < row.length; j++)
    	{
    		if(!arr.includes(row[j].innerHTML) && !row[j].classList.contains("param"))
    		{
    			arr.push(row[j].innerHTML)
    		}
    	}
    	if(arr.length == 1)
    	{
    		 checkbox.checked ? allRows[i].classList.add("common-attributes") : allRows[i].classList.remove("common-attributes")
    	}
    	delete arr
    }
}

function filterTestsByLabel(checkbox){
	// Select all the rows from both tables
	allRows = document.getElementsByClassName("all-tests-rows")

	// make their visibility false
	for(i = 0; i < allRows.length; i++)
		allRows[i].setAttribute('style','display:none')

	// This is the list of the checkboxes selected
	filterList = []
	cbs = document.getElementsByClassName("filter-checkboxes")
	for(i = 0; i < cbs.length; i++)
	{
		if(cbs[i].checked == true)
			filterList.push(cbs[i].value)
	}

	// If filterList is empty. Display all the results
	if(filterList.length == 0)
	{
		for(i = 0; i < allRows.length; i++)
			allRows[i].removeAttribute('style')
	}
	//Else display only the filtered results
	else
	{
		for(i = 0; i < allRows.length; i++)
		{
			//get second cell (the label)
			row = allRows[i]
			labels = row.children[1].innerHTML.split(',')
			console.log(labels)

			//if the benchmark has one of the selected labels
			//then make it visible
			if(labels.filter(value => filterList.includes(value)).length != 0)
				row.removeAttribute('style')
		}
	}
	console.log("FILTER LISTS IS: " + filterList)
}

function uncheckBoxes(classname){
	checkboxes = document.getElementsByClassName(classname)

	for(i = 0; i < checkboxes.length; i++)
		checkboxes[i].checked = false;

	console.log("DONE Unchecking!")
}

function showAllRuns(tableCell){
	testName = tableCell.innerHTML.trim()
	console.log(testName)
	window.location.href = '/allruns/'+testName
}

function testDetails(tableCell){
	// replace all non-digits with nothing
	originID = tableCell.innerHTML.trim().replace( /^\D+/g, '');
	console.log(originID)
	window.location.href = '/test-details/'+originID
}

function downloadAsPng(xParameter, yParameter, graphID){
	console.log("DOWNLOADING THE GRAPH?")
	graphDiv = document.getElementById(graphID);

	// downloadImage will accept the div as the first argument and an object specifying image properties as the other
	Plotly.downloadImage(graphDiv, {format: 'png', width: 800, height: 600, filename: yParameter + ' vs ' + xParameter});
}

function sendAjaxRequest(xParameter, yParameter, testname, url) {

	url_graph_map = {
		// url : graph-div-id
		'/get_data_for_graph' : 'comparison-graph',
		'/best_sku_graph' : 'best-sku-graph',

	}

	if(url == '/best_sku_graph')
		async = false;
	else
		async = true;

	$.ajax({
    	url: url,
    	async: async,
		method: "POST",
		dataType: 'json',
		contentType: "application/json",
		data: JSON.stringify({
			"xParameter" : xParameter,
			"yParameter" : yParameter,
			"testname" : testname,
		}),
	}).done(function(response){
		console.log("DONEEEEEEE")
		console.log(response)

		drawComparisonGraph(response.x_list, response.y_list, response.color_list, response.xParameter, response.yParameter, graphID = url_graph_map[url])
	})
}

function fillNormalizedDropdown(){
	//get xList from the graph
	var gd = document.getElementById('best-sku-graph')
	cpuList = gd.data[0].x

	//Fill elements of best-sku-graph's DROPDOWN list
	console.log("FILLING THE DROPDOWN LIST")

	var $normalizedList = $("#normalized-dropdown");
	$normalizedList.hide();
	//fill the list
	$.each(cpuList, function(index, cpuName){
		if(index == 0)
			$normalizedList.append("<option selected='selected' value='" + cpuName + "'>" + cpuName + "</option>");
		else
			$normalizedList.append("<option value='" + cpuName + "'>" + cpuName + "</option>");
	});
	
}

function drawComparisonGraph(xList, yList, colorList, xParameter, yParameter, graphID){
	console.log(xList + typeof(xList))
	console.log(yList + typeof(yList))

	graphDiv = document.getElementById(graphID);

	var layout = {
		xaxis: {
			type : 'category',
			title : xParameter,
		},
		yaxis: {
			title: yParameter,
		},
		title: yParameter + ' vs ' + xParameter,
	}

	data = [{
		x: xList,
		y: yList,
		marker:{
			color: colorList
		},
		haha : 'gotity',
		type: 'bar',
	}]
	Plotly.newPlot( graphDiv, data, layout);
}

function drawNormalizedGraph(graphID){
	var gd = document.getElementById(graphID)
	
	// get selected element from dropdown list
	normalizedWRT = $("#normalized-dropdown option:selected").text()

	console.log("DRAWING NORMALIZED GRAPH")
	// get the current state of the graph
	xList = gd.data[0].x
	yList = gd.data[0].y
	xParameter = gd.layout.xaxis.title.text 
	yParameter = gd.layout.yaxis.title.text
	
	$.ajax({
    	url: '/best_sku_graph_normalized',
		method: "POST",
		dataType: 'json',
		contentType: "application/json",
		data: JSON.stringify({
			"xList" : xList,
			"yList" : yList,
			"xParameter" : xParameter,
			"yParameter" : yParameter,
			"normalizedWRT" : normalizedWRT,
		}),
	}).done(function(response){
		console.log("DONEEEEEEE")
		console.log(response)
		drawComparisonGraph(response.x_list, response.y_list, response.color_list, response.xParameter, response.yParameter, graphID = 'best-sku-graph')
	})
}