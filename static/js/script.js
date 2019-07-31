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
		'/get_data_for_graph' : 'clustered-graph',
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

		if(url == '/get_data_for_graph'){
			console.log("CALLING DRAW CLUSTERED GERAPH")
			console.log(response)
			drawClusteredGraph(response.x_list_list, response.y_list_list, response.color_list, response.xParameter, response.yParameter, graphID = url_graph_map[url], response.originID_list_list, response.server_cpu_list )
		}
		else{
			console.log("CALLING DRAW OTHER GRAPH")
			drawComparisonGraph(response.x_list, response.y_list, response.color_list, response.xParameter, response.yParameter, graphID = url_graph_map[url], response.originID_list, response.server_cpu_list)
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

function drawComparisonGraph(xList, yList, colorList, xParameter, yParameter, graphID, originIDList, serverCPUList = [], higherIsBetter = "1"){
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
		showlegend: true,
	}

	// If the colorList is empty, fill the colorList with default values
	if(!colorList)
	{
		console.log("SETTING COLOR LIST")
		colorList = Array.from(xList, x=> '#1f77b4')
	}

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

	// data = [{
	// 	x: xList,
	// 	y: yList,
	// 	marker:{
	// 		color: colorList
	// 	},
	// 	originIDList : originIDList,
	// 	serverCPUList : serverCPUList,
	// 	higherIsBetter: higherIsBetter,
	// 	type: 'bar',
	// }]
	Plotly.newPlot( graphDiv, data, layout);

	if(serverCPUList.length != 0){
		// fillComparisonCheckboxes();
	}

	//Add Event on click of bar
	//Send user to "test-details" page of the respective "originID"
	graphDiv.on('plotly_click', function(data){
		console.log("CLICKED ON BAR GRAPH")
		barNumber = data.points[0].pointNumber
		originID = data.points[0].data.originID
		console.log("You clicked on " + data.points[0].data.x[barNumber])
		console.log("Which has originID " + data.points[0].data.originID)
		// window.location.href = '/test-details/'+originID
		window.open('/test-details/'+originID)
	})
}

function drawClusteredGraph(xListList=[], yListList=[], colorList=[], xParameter="X Parameter", yParameter="Y Parameter", graphID="comparison-graph", originIDListList=[], serverCPUList = []){
	console.log("DRAWING CLUSTERED GRAPH")
	graphDiv = document.getElementById('clustered-graph');

	var layout = {
		xaxis: {
			type : 'category',
			title : xParameter,
		},
		yaxis: {
			title: yParameter,
		},
		title: yParameter + ' vs ' + xParameter,
		showlegend: true,
		barmode: 'group'
	}
	
	// If the colorList is empty, fill the colorList with default values
	// if(!colorList)
	// {
	// 	console.log("SETTING COLOR LIST")
	// 	colorList = Array.from(xList, x=> '#1f77b4')
	// }

	// xListList = [['Ubuntu', 'openSUSE'],['Ubuntu', 'openSUSE'],['Ubuntu', 'MacOS']]
	// yListList = [[1,2],[3,4],[5,6]]
	// colorList = [ "FireBrick", "OrangeRed", "DodgerBlue"]
	// serverCPUList = ['Marvell-TX2-B2', 'Intel Skylake Gold', 'AMD CPU']
	// originIDListList = [[742,709], [1187,1189],[702,669]]

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
			// serverCPU : serverCPUList[index],
			// higherIsBetter: higherIsBetter,
			type: 'bar',
		})
	})
	console.log("Printing tracelist ")
	console.log(traceList) 

	data = traceList

	Plotly.newPlot( graphDiv, data, layout);

	//Add Event on click of bar
	//Send user to "test-details" page of the respective "originID"
	graphDiv.on('plotly_click', function(data){
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
	})

}

function drawNormalizedGraph(graphID, testName){
	var gd = document.getElementById(graphID)
	
	// get selected element from dropdown list
	normalizedWRT = $("#normalized-dropdown option:selected").text()

	console.log("DRAWING NORMALIZED GRAPH")
	// get the current state of the graph
	xList = []
	yList = []
	originIDList = []

	data = gd.data

	console.log("PRINTING DATA" + data)
	console.log(data[0])


	data.forEach((value, index) => {
		xList.push(data[index].x[0])
		yList.push(data[index].y[0])
		originIDList.push(data[index].originID)
	})

	xParameter = gd.layout.xaxis.title.text 
	yParameter = gd.layout.yaxis.title.text
	
	higherIsBetter = data[0].higherIsBetter

	console.log("PRINTING higher is better")
	console.log("Higher is better : " + higherIsBetter)
	// If lower is better, Inverse all the values
	if(higherIsBetter == '0'){
		console.log("Higher is better : " + higherIsBetter)
		console.log("Ylist before " + yList)
		yList.map((value, index) => {
  			yList[index] = 1/yList[index]
  		})
  		console.log("Ylist is now " + yList)
	}

	console.log("NOrmalizing wrt" + normalizedWRT)

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
			"originIDList": originIDList,
			"testName": testName,
		}),
	}).done(function(response){
		console.log("DONEEEEEEE")
		console.log(response)
		drawComparisonGraph(response.x_list, response.y_list, response.color_list, response.xParameter, response.yParameter, graphID = 'best-sku-graph', response.originID_list, serverCPUList = [],  higherIsBetter = response.higher_is_better)
	})
}