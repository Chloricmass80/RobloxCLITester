-- Consider this script to be server-side.
local HttpService = game:GetService("HttpService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Workspace = game:GetService("Workspace")
RecurseModule = ReplicatedStorage:WaitForChild("RecurseAudioEngine")

tests = {}

type Condition = {
    AddCheck : (self: Condition, checkName: string, expectedOutput: any) -> ();
    RunCheck : (self: Condition, checkName: string, input: any) -> (boolean, string?);
    RunChecks : (self: Condition, input : {any}) -> ();
    GetCheckNames : (self: Condition) -> ({string});
    GetResults : (self: Condition) -> (boolean, string?);
}

-- tables or buffers printed to CLI are memory adresses, this just makes it debuggable.
function betterToStr(val : any) : string
    local valType = typeof(val)
    if valType == "table" then
        local str = "{" 
        for key, subVal in pairs(val) do
            if typeof(key) == "number" then
                str = string.format("%s%s, ", str, betterToStr(subVal))
            else
                str = string.format("%s%s = %s, ", str, betterToStr(key), betterToStr(subVal))
            end
        end
        str = str:sub(1, str:len() - 2)
        str = string.format("%s}", str)
        return str
    elseif valType == "buffer" then
        return "buffer"
    else
        return tostring(val)
    end
end

-- equivalence between tables from value to value, ignores memory adress equivalence
local function deepEqual(a, b)
    if type(a) ~= type(b) then return false end
    if type(a) ~= "table" then return a == b end

    for k, v in pairs(a) do
        if not deepEqual(v, b[k]) then return false end
    end
    for k in pairs(b) do
        if a[k] == nil then return false end
    end

    return true
end



local Condition = {}
Condition.__index = Condition

function Condition.new() : Condition
    local self = setmetatable({
        _checks = {};
        _passed = true;
        _checkFailMsgs = {};
    }, Condition)

    return self :: Condition
end

function Condition:AddCheck(checkName:string, expectedOutput:any) : ()
    table.insert(self._checks, {checkName, expectedOutput, false})
end

function Condition:_CheckCommon(check, input)
    if check[3] == true then
        return
    end

    local expectedOutput = check[2]
    local checkName = check[1]
    local checkPass = nil
    if deepEqual(input, expectedOutput) then
        checkPass = true
    else
        checkPass = false
        table.insert(self._checkFailMsgs, string.format("'%s check' expected %s, got %s.", checkName, betterToStr(expectedOutput), betterToStr(input)))
    end

    check[3] = true
    self._passed = self._passed and checkPass
end

function Condition:RunCheck(checkName:string, input:any)
    local check = nil
    for _, chk in ipairs(self._checks) do
        if chk[1] == checkName then
            check = chk
            break
        end
    end

    assert(check, string.format("Check by name %s not found", checkName))

    self:_CheckCommon(check, input)
end

function Condition:_RunCheckByIndex(checkIndex:number, input:any)
    local check = self._checks[checkIndex]
    self:_CheckCommon(check, input)
end

function Condition:RunChecks(inputs : {any})
    for i, _ in ipairs(self._checks) do
        local input = inputs[i]
        
        self:_RunCheckByIndex(i, input)
    end
end


function Condition:GetCheckNames() : {string}
    local checkNameArray = {}
    for _, check in ipairs(self._checks) do
        table.insert(checkNameArray, check[1])
    end

    return checkNameArray
end

function Condition:GetResults() : (boolean, string?)
    if #self._checkFailMsgs == 0 then
        return self._passed
    end
    local errMsg = ""
    for i, msg in ipairs(self._checkFailMsgs) do
        if i == #self._checkFailMsgs then
            errMsg = string.format("%s%s", errMsg, msg)
        else
            errMsg = string.format("%s%s\n", errMsg, msg)
        end
    end

    return self._passed, errMsg
end


TestClass = {}
TestClass.__index = TestClass

function TestClass.new(name:string, actionFunc: () -> ...any, passCondition : (...any) -> (boolean, string?))
    local self = setmetatable({
        _actionFunc = actionFunc;
        _passCondition = passCondition;
        _name = name;
        _hasPassed = nil;
        _failReason = nil;
        _error = nil;
    }, TestClass)

    tests[name] = self

    return self
end

function TestClass:Execute() : ...any
    local results = table.pack(pcall(self._actionFunc))
    local passed = results[1]
    table.remove(results, 1)
    if passed then
        passed, results = self._passCondition(table.unpack(results))
    else
        self._failReason = "runtime error"
        self._error = results[1]
        self._hasPassed = passed
        return
    end
    if not passed then
        self._failReason = "did not meet pass conditions"
    end
    self._error = results
    self._hasPassed = passed
end



-------------------------- TESTS --------------------------

----- EXAMPLE TEST -----
--[[
function ExampleAction()
    * action to be tested*

    return result1, result2
end

function ExampleCondition(result1, result2)
    local condition = Condition.new()
    
    condition:AddCheck("ExampleCheckName", "ExampleExpectedValue")
    condition:AddCheck("ExampleCheckName2", "ExampleExpectedValue2")

    condition:RunChecks({result1, result2})  -- ex: if result1 ~= "ExampleExpectedValue", check failed
end
TestClass.new("ExampleTest", ExampleAction, ExampleCondition)
--]]
----- EXAMPLE TEST -----



--  Tests go here --



-------------------------- HANDLING OUTPUT --------------------------
resultDict = {}
for name, test in pairs(tests) do
    test:Execute()

    resultDict[name] = {test._hasPassed, test._failReason, test._error}
end

return resultDict