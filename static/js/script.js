function hideCommon() {
	$checkboxCommon = $('#checkbox-common')

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
    		 $checkboxCommon.prop('checked') ? allRows[i].classList.add("common-attributes") : allRows[i].classList.remove("common-attributes")
    	}
    	delete arr
    }
}

function filterTestsByLabel(){
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

	// Get normalized WRT if graph exists, or choose the first one
	// Graph does not exist initially when we load/refresh page
	$dropdownMenu = $('#reference-for-normalized-dropdown')
	$firstNormalized = $dropdownMenu.children()[1].innerHTML
	
	graphDiv = document.getElementById('best-of-all-graph')
	normalizedWRT = graphDiv.data ? graphDiv.data.normalizedWRT : $firstNormalized
	
	//Draw new best_of_all_graph according to filters
	drawBestOfAllGraph(normalizedWRT)
}

function drawBestOfAllGraph(normalizedWRT){
	console.log("DRAWING BEST GRAPH")
	console.log(normalizedWRT)

	// Get date filters
	$fromDate = $('#from-date').val()
	$toDate = $('#to-date').val()

	// Selected tests which are to be displayed on the graph
	allRows = $("tr").filter(function() { return $(this).css("display") != "none" })

	selectedTestsList = []
	for(i = 0; i < allRows.length; i++)
		selectedTestsList.push(allRows[i].children[0].children[0].innerHTML)

	data = {
		'normalizedWRT' : normalizedWRT,
		'test_name_list' : selectedTestsList,
		'from_date_filter' : $fromDate,
		'to_date_filter' : $toDate,
		'resultTypeFilter' : $('#resultype-filter option:selected').val(),
	}

	Plotly.purge('best-of-all-graph')

	// Set html to loading circle
	$("#best-of-all-graph").html(("<div class='loading-circle text-center'><div class='spinner-border text-center' role='status'><span class='sr-only'>Loading...</span></div></div>"));

	$.ajax({
    	url: '/best_of_all_graph',
		method: "POST",
		dataType: 'json',
		contentType: "application/json",
		data: JSON.stringify(data),
	}).done(function(response){
		$('.loading-circle').remove()

		// Expand the collapse element
		$('#bestGraphCollapse').addClass('show')

		console.log("DONEEEEEEE BEST OF ALL")
		console.log(response)

		// Remove the Loading... message
		$("#best-of-all-graph").empty()
		drawClusteredGraph(response, graphID = 'best-of-all-graph')
	})
}

function downloadAsPng(filename, graphID){
	console.log("DOWNLOADING THE GRAPH")
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
		'/sku_comparison_graph' : 'sku-comparison-graph',
		'/best_sku_graph' : 'best-sku-graph',
		'/best_sku_graph_normalized' : 'best-sku-graph',
		'/timeline_graph' : 'timeline-graph',
	}

	Plotly.purge(url_graph_map[url])

	// Set html to loading circle
	$('#'+url_graph_map[url]).html("<div class='loading-circle-" + url_graph_map[url] + " text-center'><div class='spinner-border text-center' role='status'><span class='sr-only'>Loading...</span></div></div>")


	$.ajax({
    	url: url,
		method: "POST",
		dataType: 'json',
		contentType: "application/json",
		data: JSON.stringify(ajaxData),

	}).done(function(response){
		// Remove all the loading circles first
		$(".loading-circle-" + url_graph_map[url]).remove()

		console.log("DONEEEEEEE")
		console.log(response)

		if(url == '/sku_comparison_graph') {
			drawClusteredGraph(response, graphID = url_graph_map[url])
		}
		else if(url == '/timeline_graph') {
			drawScatterPlot(response, graphID = url_graph_map[url])
		}
		else {
			console.log("CALLING DRAW OTHER GRAPH")
			drawComparisonGraph(response, graphID = url_graph_map[url])
		}

		// Fill the dropdown after the graph data is available
		if(url == '/best_sku_graph')
			fillNormalizedDropdown();
	})
}

function fillNormalizedDropdown(){
	//make "Absolute" as "checked"
	var $radios = $('input[type=radio][name=typeOfGraph]')
	$radios.filter('[value=Absolute]').prop('checked', true);

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

	// Clear all the earlier values
	$normalizedList.empty()

	//hide it
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

	console.log("higherIsBetter: " + higherIsBetter);
	// If it is a normalized graph, then change the title
	if(graphID == 'best-sku-graph' && $('#normalized-radio-button')[0].checked)
		title = "Best results normalized w.r.t. " + $('#normalized-dropdown option:selected').text()
	else if(graphID == 'best-sku-graph'){
		higherIsBetterText = higherIsBetter == '1' ? "<br>(Higher is Better)" : "<br>(Lower is Better)"

		title = yParameter + ' vs ' + xParameter + higherIsBetterText
	}
	else
		title = yParameter + ' vs ' + xParameter

	var layout = {
		xaxis: {
			type : 'category',
			title : xParameter,
			automargin : true, 
		},
		yaxis: {
			title: yParameter + ' (' + yAxisUnit + ')',
			automargin : true, 
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

	Plotly.react(graphDiv, data, layout);

	//remove the previous listeners to avoid multiple function calls on click
	graphDiv.removeAllListeners('plotly_click')

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

function drawClusteredGraph(response, graphID) {
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
	normalizedWRT = response.normalized_wrt
	
	console.log("DRAWING CLUSTERED GRAPH")
	graphDiv = document.getElementById(graphID);

	if(!visibleList)
		visibleList = Array.from(colorList, v=> true)

	if(graphID == 'best-of-all-graph'){
		title = "Best results normalized w.r.t. " + normalizedWRT 
		if ($('#resultype-filter option:selected').val() != "")
			title = title + "<br>(" + $('#resultype-filter option:selected').val() + ")"

		titlefont = {
    		"size": 24,
  		}
	}
	else{
		title = yParameter +'(' + yAxisUnit + ')' + ' vs ' + xParameter
		titlefont = 24
	}

	var layout = {
		xaxis: {
			type : 'category',
			title : xParameter,
			automargin : true, 
		},
		yaxis: {
			title: yParameter,
			automargin : true,
		},
		titlefont: titlefont,
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

	// Manually set a normalizedWRT key to the data
	data.normalizedWRT = normalizedWRT

	if(graphID == 'best-of-all-graph')
		Plotly.newPlot( graphDiv, data, layout);
	else
		Plotly.react( graphDiv, data, layout);

	// Draw Reference Line if graphID is 'best-of-all-graph'
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
			// Comparison on similar types for safety
			index = barData.data.x.findIndex(item => String(item) === String(barData.x))
			console.log("INDEX = " + index)

			originID = barData.data.originIDList[index]
			console.log("ORIGIN ID IS" + originID)
			window.open('/test-details/'+originID)
		}
	}

	//remove the previous listeners to avoid multiple function calls on click
	graphDiv.removeAllListeners('plotly_click')

	//Add Event on click of bar
	//Send user to "test-details" page of the respective "originID"
	graphDiv.on('plotly_click', openTestDetailsPage)
}

function drawNormalizedGraph(graphID, testname, alreadyNormalized=false) {
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

	if(alreadyNormalized == false) {
		// If lower is better, Inverse all the values
		if(higherIsBetter == '0'){
			// map applies the function passed to each element of the list
			yList.map((value, index) => {
				yList[index] = 1/yList[index]
			})
		}
	}
	
	data = {
		"xList" : xList,
		"yList" : yList,
		"xParameter" : xParameter,
		"yParameter" : yParameter,
		"normalizedWRT" : normalizedWRT,
		"originIDList": originIDList,
		"testname": testname,
	}

	sendAjaxRequest(data, '/best_sku_graph_normalized')
}

function drawLineGraph(response, graphID) {
	console.log("DRAWING LINE GRAPH")
	console.log(response)
	xListList = response.x_list_list 
	yListList = response.y_list_list 
	legendList = response.legend_list ? response.legend_list : []
	xParameter = response.xParameter
	yParameter = response.yParameter
	graphTitle = response.graphTitle

	// List  of traces to be drawn
	traceList = []
	xListList.forEach((value, index) => {
		traceList.push({
			type: 'scatter',
			x: xListList[index],
			y: yListList[index],
			mode: 'lines',
			name: legendList[index],
			line: {
				width: 3,
			}				
		})
	}) 

	layout = {
		xaxis: {
			title : xParameter,
			rangeslider : {
				bordercolor : "#eee",
				borderwidth : 2,
				thickness : 0.07,
			},
		},
		yaxis: {
			title: yParameter,
		},
		title: graphTitle,
	};

	Plotly.newPlot(graphID, traceList, layout);
}

function drawStackGraph(response, graphID) {
	console.log("Drawing Stack Graph")
	console.log(response)

	xList = response.x_list
	yListList = response.y_list_list
	legendList = response.legend_list
	xParameter = response.xParameter
	yParameter = response.yParameter
	graphTitle = response.graphTitle

	// List  of traces to be drawn
	traceList = []
	yListList.forEach((value, index) => {
		traceList.push({
			x: xList,
	  		y: yListList[index],
  			name: legendList[index],
  			type: 'bar'
		})
	}) 

	// Bar-mode is stack
	layout = {
		xaxis: {
			title : xParameter,
			rangeslider : {
				bordercolor : "#eee",
				borderwidth : 2,
				thickness : 0.07,
			},
		},
		yaxis: {
			title: yParameter,
		},		
		barmode: 'stack',
		title : graphTitle,
	};

	Plotly.newPlot(graphID, traceList, layout);
}

function drawHistogram(response, graphID) {
	console.log("DRAWING HISTOGRAM")
	
	xListList = response.x_list_list
	legendList = response.legend_list
	binSize = response.bin_size
	xParameter = response.xParameter
	yParameter = response.yParameter
	graphTitle = response.graphTitle

	// List  of traces to be drawn
	traceList = []
	xListList.forEach((value, index) => {
		traceList.push({
			x: xListList[index],
    		type: 'histogram',
    		xbins: { 
			    size: binSize[index], 
			}
		})
	}) 

	layout = {
		xaxis: {
			title : xParameter,
		},
		yaxis: {
			title: yParameter,
		},
		title: graphTitle,
	};


	Plotly.newPlot(graphID, traceList, layout);

}

function drawBarGraph(response, graphID) {
	console.log("DRAWING BarGraph")	

	xList = response.x_list	
	yList = response.y_list
	xParameter = response.xParameter
	yParameter = response.yParameter


	var data = [{
		x: xList,
	    y: yList,
	    type: 'bar'
	}];

	layout = {
		xaxis: {
			title : xParameter,
		},
		yaxis: {
			title: yParameter,
		},
		title: yParameter + ' vs ' + xParameter,
	};


	Plotly.newPlot(graphID, data, layout);
}

function drawHeatmap(response, graphID) {
	console.log("DRAWING HISTOGRAM")

	xList = response.x_list	
	yList = response.y_list
	zListList = response.z_list_list
	xParameter = response.xParameter
	yParameter = response.yParameter
	graphTitle = response.graphTitle

	if (graphTitle == "" || !graphTitle) {
		graphTitle = "Heatmap"
	}

	var data = [{
		x : response.x_list,
		y : response.y_list,
		z: response.z_list_list,
	    type: 'heatmap',
	    zmin : 0,
	    zmax : 100,
	}];

	layout = {
		xaxis: {
			title : xParameter,
			rangeslider : {
				bordercolor : "#eee",
				borderwidth : 2,
				thickness : 0.07,
			},
		},
		yaxis: {
			title: yParameter,
		},
		title: graphTitle,
	};


	Plotly.newPlot(graphID, data, layout);
}

function drawComboGraph(response, graphID) {
	console.log("Drawing Combo Graph")
	console.log(response)
	console.log(graphID)
	graphData1 = response['graph_1_data']

	graphData2 = response['graph_2_data']

	// Stack Graph
	traceList = []
	graphData1.y_list_list.forEach((value, index) => {
		traceList.push({
			x: graphData1.x_list,
			y: graphData1.y_list_list[index],
			name: graphData1.legend_list[index],
			type: 'bar',
			xaxis:'x',
			yaxis:'y',
		})
	})

	graphData2.x_list_list.forEach((value, index) => {
		traceList.push({
			type: 'scatter',
			x: graphData2.x_list_list[index],
			y: graphData2.y_list_list[index],
			mode: 'lines',
			name: graphData2.legend_list[index],
			line: {
				width: 3,
			},
			xaxis:'x',
			yaxis:'y2',
		})
	})

	var data = traceList

	var layout = {
		showlegend: true,
		legend: {
			"orientation": "h",
		},
		xaxis: {
			title : {
				text: graphData1.xParameter,
				standoff : 50,
			}
		},

		yaxis: {title: graphData1.yParameter},
		yaxis2: {
			title: graphData2.yParameter,
			autorange: true,
			titlefont: {color: 'rgb(148, 103, 189)'},
			tickfont: {color: 'rgb(148, 103, 189)'},
			overlaying: 'y',
			side: 'right',
		},
		barmode: 'stack',
		title: response.graphTitle,
	  };

	Plotly.newPlot(graphID, data, layout);
}

function drawScatterPlot(response, graphID) {
	console.log("Drawing Scatter Plot")
	console.log(response)
	xListList = response.x_list_list 
	yListList = response.y_list_list
	originIDListList = response.originID_list_list 
	legendList = response.legend_list ? response.legend_list : []
	xParameter = response.xParameter
	yParameter = response.yParameter
	graphTitle = response.graphTitle
	xListOrder = response.x_list_order ? response.x_list_order : []

	// List  of traces to be drawn
	traceList = []
	xListList.forEach((value, index) => {
		traceList.push({
			type: 'scatter',
			x: xListList[index],
			y: yListList[index],
			originIDList : originIDListList[index],
			mode: 'lines+markers',
			name: legendList[index],
			line: {
				width: 3,
			},
			text: legendList[index],
		})
	})

	layout = {
		xaxis: {
			title : xParameter,
			categoryorder : "array",
			categoryarray : xListOrder,
		},
		yaxis: {
			title: yParameter,
		},
		title: graphTitle,
	};

	Plotly.newPlot(graphID, traceList, layout);

	function openTestDetailsPage(data){
		console.log("PRINTING DATA")
		console.log(data)

		console.log("\nClicked on Point")
		allPoints = data.points
		for(i = 0; i < allPoints.length; i++){
			pointData = allPoints[i]
			console.log(allPoints[i])
			// Comparison on similar types for safety
			index = pointData.data.x.findIndex(item => String(item) === String(pointData.x))
			console.log("INDEX = " + index)

			originID = pointData.data.originIDList[index]
			console.log("originID = " + originID)
			window.open('/test-details/' + originID)
		}
	}

	let graphDiv = document.getElementById(graphID);
	//remove the previous listeners to avoid multiple function calls on click
	graphDiv.removeAllListeners('plotly_click')

	//Add Event on click of bar
	//Send user to "test-details" page of the respective "originID"
	graphDiv.on('plotly_click', openTestDetailsPage)

}
