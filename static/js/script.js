function hideCommon(checkbox) {
    console.log("Hide common is yet to be implemented")
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

function uncheckBoxes(){
	checkboxes = document.getElementsByClassName("diff-checkbox")

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
	originID = tableCell.innerHTML.trim()
	console.log(originID)
	window.location.href = '/test-details/'+originID
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