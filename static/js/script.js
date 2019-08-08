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
			if(labels.filter(value => filterList.includes(value)).length != 0){
				row.removeAttribute('style')
			}
		}
	}
	console.log("FILTER LISTS IS: " + filterList)

	//Draw new best_of_all_graph according to filters
	drawBestOfAllGraph()

}

function drawBestOfAllGraph(data = {}){
	console.log("DRAWING BEST GRAPH")

	// Selected tests which are to be displayed on the graph
	allRows = $("tr").filter(function() { return $(this).css("display") != "none" })

	selectedTestsList = []
	for(i = 0; i < allRows.length; i++)
		selectedTestsList.push(allRows[i].children[0].innerHTML)

	// Normalized (Reference CPU Manufacturer)
	normalizedWRT = $('#reference-for-normalized option:selected').text()

	data = {
		'normalizedWRT' : normalizedWRT,
		'test_name_list' : selectedTestsList,
	}

	// Show "Loading..." message before the graph loads 
	$("#best-of-all-graph").html("Loading Graph...");

	$.ajax({
    	url: '/best_of_all_graph',
    	// async: async,
		method: "POST",
		dataType: 'json',
		contentType: "application/json",
		data: JSON.stringify(data),
	}).done(function(response){
		console.log("DONEEEEEEE BEST OF ALL")
		console.log(response)

		// Remove the Loading... message
		$("#best-of-all-graph").empty()
		drawClusteredGraph(response, graphID = 'best-of-all-graph')
	})
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

function downloadAsPng(filename, graphID){
	console.log("DOWNLOADING THE GRAPH?")
	graphDiv = document.getElementById(graphID);

	if(graphID == "best-sku-graph")
		filename = "Best " + filename;

	// downloadImage will accept the div as the first argument and an object specifying image properties as the other
	Plotly.downloadImage(graphDiv, {format: 'png', width: 800, height: 600, filename: filename});
}

function downloadAsCsv(filename, data, $form){
	// data will be in the form of dictionary of lists
	// key->[list]

	console.log("Downloading as CSV, manually clicking on the link")
	data_string = JSON.stringify({ 'data': data, 'filename': filename})
	$form.append($("<input name= 'data' type= 'text' value = '" + data_string + "'/>"))

	console.log($form)
	$form.submit()

	// Clear the contents of the form
	$form.empty()

}

function sendAjaxRequest(ajaxData, url) {

	url_graph_map = {
		// url : graph-div-id
		'/get_data_for_graph' : 'clustered-graph',
		'/best_sku_graph' : 'best-sku-graph',
		'/best_sku_graph_normalized' : 'best-sku-graph',
	}

	// Async is kept false as we have to call fillNormalizedDropdown only after graph is drawn!
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
		data: JSON.stringify(ajaxData),

	}).done(function(response){
		console.log("DONEEEEEEE")
		console.log(response)

		if(url == '/get_data_for_graph'){
			console.log("CALLING DRAW CLUSTERED GERAPH")
			console.log(response)
			drawClusteredGraph(response, graphID = url_graph_map[url])
		}
		else{
			console.log("CALLING DRAW OTHER GRAPH")
			drawComparisonGraph(response, graphID = url_graph_map[url])
		}
	})
}

function fillNormalizedDropdown(){
	//get xList from the graph
	var gd = document.getElementById('best-sku-graph')
	// cpuList = gd.data[0].x
	cpuList = []

	data = gd.data

	data.forEach((value, index) => {
		cpuList.push(data[index].x[0])
	})


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

function drawComparisonGraph(response, graphID){
	xList = response.x_list
	yList = response.y_list
	colorList = response.color_list
	xParameter = response.xParameter
	yParameter = response.yParameter
	originIDList = response.originID_list
	serverCPUList = response.server_cpu_list ? response.server_cpu_list : []
	higherIsBetter = response.higher_is_better
	yAxisUnit = response.y_axis_unit

	graphDiv = document.getElementById(graphID);

	// If it is a normalized graph, then change the title
	if(graphID == 'best-sku-graph' && $('#normalized-checkbox')[0].checked)
		title = "Best results normalized w.r.t. " + $('#normalized-dropdown option:selected').text()
	else
		title = yParameter + ' vs ' + xParameter

	var layout = {
		xaxis: {
			type : 'category',
			title : xParameter,
		},
		yaxis: {
			title: yParameter + ' (' + yAxisUnit + ')',
		},
		title: title,
		showlegend: true,
	}

	// List  of traces to be drawn
	traceList = []
	xList.forEach((value, index) => {
		traceList.push({
			x: [xList[index]],
			y: [yList[index]],
			marker: {
				color: colorList[index],
			},
			name: xList[index], //name in the legend
			originID : originIDList[index],
			serverCPU : serverCPUList[index],
			higherIsBetter: higherIsBetter,
			type: 'bar',
		})
	})
	console.log("Printing tracelist ")
	console.log(traceList) 

	data = traceList

	Plotly.newPlot(graphDiv, data, layout);

	//Add Event on click of bar
	//Send user to "test-details" page of the respective "originID"
	graphDiv.on('plotly_click', function(data){
		console.log("CLICKED ON BAR GRAPH")
		barNumber = data.points[0].pointNumber
		originID = data.points[0].data.originID
		console.log("You clicked on " + data.points[0].data.x[barNumber])
		console.log("Which has originID " + data.points[0].data.originID)

		window.open('/test-details/'+originID)
	})
}

function drawClusteredGraph(response, graphID){
	xListList = response.x_list_list
	yListList = response.y_list_list
	colorList = response.color_list
	xParameter = response.xParameter
	yParameter = response.yParameter
	originIDListList = response.originID_list_list
	serverCPUList = response.server_cpu_list
	referenceColor = response.reference_color
	visibleList = response.visible_list
	yAxisUnit = response.y_axis_unit

	console.log("DRAWING CLUSTERED GRAPH")
	graphDiv = document.getElementById(graphID);

	if(!visibleList)
		visibleList = Array.from(colorList, v=> true)

	if(graphID == 'best-of-all-graph')
		title = "Best results normalized w.r.t. " + $('#reference-for-normalized option:selected').text()
	else
		title = yParameter +'(' + yAxisUnit + ')' + ' vs ' + xParameter

	var layout = {
		xaxis: {
			type : 'category',
			title : xParameter,
		},
		yaxis: {
			title: yParameter,
		},
		title: title,
		showlegend: true,
		barmode: 'group',
	}
	
	// List  of traces to be drawn
	traceList = []
	xListList.forEach((value, index) => {
		traceList.push({
			x: xListList[index],
			y: yListList[index],
			marker: {
				color: colorList[index],
			},
			name: serverCPUList[index], 	//name of the CPU (Marvell, Intel, etc.) in the legend
			originIDList : originIDListList[index],
			type: 'bar',
			visible : visibleList[index],
		})
	})
	console.log("Printing tracelist ")
	console.log(traceList) 

	data = traceList

	Plotly.newPlot( graphDiv, data, layout);

	// Draw Reference Line if graphID is 'best-of-all-graph'
	console.log("REDRAWING ANNA")
	if(graphID == 'best-of-all-graph'){
		function drawReferenceLine(data){	
			console.log("REDRAWING REFERENCE LINE")	
			// delete the earlier shapes

			console.log("SHAPES BEFORE")
			console.log(graphDiv.layout.shapes)

			graphDiv.layout.shapes = []
			console.log("SHAPES AFTER DELETION")
			console.log(graphDiv.layout.shapes)


			// Redraw the graph to get xStart and xEnd
			Plotly.update(graphDiv, graphDiv.data, graphDiv.layout).then(() => {
					// get the new endpoints
				xStart = graphDiv.layout.xaxis.range[0]
				xEnd = graphDiv.layout.xaxis.range[1]
			
				shapes = [{
					type:'line',
					xref:'paper',
					yref: 'y',
					x0: xStart,
					y0: 1, 
					x1: xEnd,
					y1: 1,
					opacity: 0.7,
					line: {
						color: referenceColor,
						width: 5,
					},
				}]

				// set new shape
				graphDiv.layout.shapes = shapes

				console.log("SHAPES AFTER")
				console.log(graphDiv.layout.shapes)

				// Redraw again to get Perfect reference line
				Plotly.update(graphDiv, graphDiv.data, graphDiv.layout).then(() => {console.log("DONE REDRAWING REFERENCE LINE")})

			});
		}

		//Draw the initial reference Line
		drawReferenceLine({})

		// If legend is clicked, graph is resized
		// Therefore, redraw the reference Line
		graphDiv.on('plotly_legendclick', drawReferenceLine)
	}

	function openTestDetailsPage(data){
		console.log("PRINTING DATA")
		console.log(data)

		console.log("\nClicked ON BAR GRAPH")
		allBars = data.points
		for(i = 0; i < allBars.length; i++){
			barData = allBars[i]
			console.log(allBars[i])
			index = barData.data.x.indexOf(barData.x)
			console.log("INDEX = " + index)

			originID = barData.data.originIDList[index]
			console.log("ORIGIN ID IS" + originID)
			window.open('/test-details/'+originID)
		}
	}

	//Add Event on click of bar
	//Send user to "test-details" page of the respective "originID"
	graphDiv.on('plotly_click', openTestDetailsPage)

}

function drawNormalizedGraph(graphID, testName){
	console.log("DRAWING NORMALIZED GRAPH")

	var gd = document.getElementById(graphID)
	
	// get selected element from dropdown list
	normalizedWRT = $("#normalized-dropdown option:selected").text()

	// get the current state of the graph
	xList = []
	yList = []
	originIDList = []

	data = gd.data

	// Fill the xList, yList and originIDList from the Graph's data
	data.forEach((value, index) => {
		xList.push(data[index].x[0])
		yList.push(data[index].y[0])
		originIDList.push(data[index].originID)
	})

	// get x and y parameters
	xParameter = gd.layout.xaxis.title.text 
	yParameter = gd.layout.yaxis.title.text

	// Remove the 'yAxisUnit' part from the yParameter
	yParameter = yParameter.substring(0, yParameter.indexOf('('))
	
	// get Higher is better value from the graph data
	higherIsBetter = data[0].higherIsBetter
	console.log("Higher is better : " + higherIsBetter)

	// If lower is better, Inverse all the values
	if(higherIsBetter == '0'){
		// map applies the function passed to each element of the list
		yList.map((value, index) => {
  			yList[index] = 1/yList[index]
  		})
	}

	ajaxData = {
		"xList" : xList,
		"yList" : yList,
		"xParameter" : xParameter,
		"yParameter" : yParameter,
		"normalizedWRT" : normalizedWRT,
		"originIDList": originIDList,
		"testName": testName,
	}

	sendAjaxRequest(ajaxData, '/best_sku_graph_normalized')
}