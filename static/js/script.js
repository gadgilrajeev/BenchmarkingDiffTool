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
	allRows = document.getElementsByClassName("all-tests-rows")

	for(i = 0; i < allRows.length; i++)
		allRows[i].setAttribute('style','display:none')

	console.log("GAYAB")


	filterList = []
	cbs = document.getElementsByClassName("filter-checkboxes")
	for(i = 0; i < cbs.length; i++)
	{
		if(cbs[i].checked == true)
			filterList.push(cbs[i].value)
	}
	if(filterList.length == 0)
	{
		for(i = 0; i < allRows.length; i++)
			allRows[i].removeAttribute('style')
	}
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

function drawGraph(columns_data){

	function toList(str){
		return str.replace(/[\[\]\']/g,'').split(',')
	}


	function arrayRemove(arr, value) {
		return arr.filter(function(ele){
			return ele != value;
		});
	}

	originID_list = arrayRemove(Object.keys(columns_data), 'qualifier');

	console.log(typeof(originID_list))
	console.log(originID_list)
	console.log(originID_list[0])
	console.log(typeof(columns_data))
	console.log(columns_data)
	
	graphDiv = document.getElementById('comparison-graph');
	data = [{
		x: originID_list,
		y: [1, 2,3,4],
		type: 'bar' 
	}]
	Plotly.plot( graphDiv, data);

	return columns_data

}

function addTest(){
	console.log("ADDING TEST")
	form = document.getElementById('comparison-form-elements')
	testCount = form.childElementCount

	newDiv = document.createElement('div')
	
	newLabel = document.createElement('label')
	newLabel.setAttribute('style','font-family: Bookman Old Style')
	newLabel.setAttribute('for','test_'+(testCount+1))
	newLabel.innerHTML='Test '+ (testCount+1)
	
	newInput = document.createElement('input')
	newInput.setAttribute('type',"text")
	newInput.setAttribute('id',"test_"+(testCount+1))
	newInput.setAttribute('name',"test_"+(testCount+1))
	newInput.setAttribute('placeholder','Enter Test Number')

	newDiv.appendChild(newLabel)
	newDiv.appendChild(newInput)
	
	if(testCount == 2)
	{
		lastDiv = document.getElementById('last-div')
	
		newInput = document.createElement('button')
		newInput.setAttribute('id','remove-test')
		newInput.setAttribute('class','red')
		newInput.setAttribute('type','button')
		newInput.setAttribute('onclick','removeTest()')
		newInput.innerHTML = "Remove a Test"

		var submitButton = document.getElementById('comparison-submit-button')
		lastDiv.removeChild(submitButton)

		lastDiv.appendChild(newInput)
		lastDiv.appendChild(submitButton)
	}

	form.appendChild(newDiv)
	return false
}

function removeTest(){
	testCount = form.childElementCount
	form.removeChild(form.lastChild)
	if(testCount == 3)
	{
		lastDiv = document.getElementById('last-div')
		removeButton = document.getElementById('remove-test')

		lastDiv.removeChild(removeButton)	
	}
	return false
}