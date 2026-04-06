This tool does a few things. It's main purpose is to streamline unit testing with the Rojo workflow. While other projects exist that do the same thing, this is meant to be light-weight and easy to use. All it requires is a command line, most any Python version, and an API key, then you just run the .py file under the tests directory, and you get the results for your tests. We'll go over how to make a test in a bit.

# Requirements
- Python V3.9 or newer
- An API key with valid perms
- That's it.


# Setup
1. Clone the Repository
2. Place directories into your project as layed out in the "Project Structure" section
3. Create a stub test place. **DO NOT** use a universe or place you care about, **IT WILL BE OVERWRITTEN AND DESTROYED!!**
4. Create a valid API Key with valid perms. Will be discussed in more depth if you're unsure on how to do that.
5. Clone "example.env" to "local.env" and fill in the values
6. Create your unit tests
7. Run test_handler.py
8. Bathe in the unit testing glory!

# Writing a Test:
You can find the same explanation under the `Tests.luau` file itself, but I'll put it here as well and explain some things.

To create a test, you don't have to ever touch `test_handler.py`. Everything is accessible through `Tests.luau`, you shouldn't need to touch the Python file unless you want to change how things are formatted or more advanced things.

Here is an example test structure for reference:

```lua
function ExampleAction()
    --*action to be tested*

    return result1, result2
end

function ExampleCondition(result1, result2)
    local condition = Condition.new()
    
    condition:AddCheck("ExampleCheckName", "ExampleExpectedValue")
    condition:AddCheck("ExampleCheckName2", "ExampleExpectedValue2")

    condition:RunChecks({result1, result2})  -- ex: if result1 ~= "ExampleExpectedValue", check failed

    return condition:GetResults()
end
TestClass.new("ExampleTest", ExampleAction, ExampleCondition)
```

## Explanation:
You first must create an action function. This is the action the test will perform, and later will be examined for validity. So if you wanted to test the addition of two numbers, the action function would be:

```lua
function ExampleAction()
    local result1 = 1 + 2

    return result1
end
```

Then you must create a condition function. This takes what the action function returned as parameters, and then tests it based on what the expected output is. It must always returns 'condition:GetResults()'. Continuing the addition example:

```lua
function ExampleCondition(result1)
    local condition = Condition.new()
    
    condition:AddCheck("SumCheck", 3)

    condition:RunChecks({result1})  -- ex: if result1 ~= 3, check failed

    return condition:GetResults()
end
```

Then you need a boilerplate line to create the test:

```lua
TestClass.new("ExampleTest", ExampleAction, ExampleCondition)
```

And that's it!

## Further Notes:

Action functions are designed to handle errors, so if you expect something might error, put it in the action function. This includes requiring modules and things like that. It is **highly recommended** any modules you are testing are required in the action functions each time they are needed and not outside of them, that way if the module has a runtime error it won't crash the test script, it'll just fail the test.

`Condition:AddCheck()` takes a test name, and then an expected output.
`Condition:RunChecks()` will run the checks in order of creation, it also expects the outputs in order of check creation. So if you created two tests, the result for the first one is in index 1, and the result of the second should be in index 2.

Alternatively, you can do `Condition:RunCheck()` if you want, it's more verbose but more readable. It takes a check name as the first argument, and then the result.

A failure in the testing script itself will return as an overall error in the CLI, not a test error, so if you did this step wrong you'll know explicitly. If you messed up the syntax within the action function though, it will error as a test, and not overall, so beware if your test is failing even though the system works fine, you might have written the action incorrectly.

# Creating an API Key

go to this website to create a Roblox Open Cloud API Key:
[API Key Creation](https://create.roblox.com/dashboard/credentials)

Give it an appropriate name, then give it the following permissions:

- universe-places:write
- universe.place.luau-execution-sessions:read
- universe.places.luau-execution-sessions:write
- universe:write

It is recommended you restrict these permissions to your stub testing place so you don't accidentally nuke something important. Because as soon as you run this CLI tester it will completely overwrite whatever place you tell it to with testing nonsense.

After you configure perms and create it, copy the API key and paste it into your local.env. Alternatively you can create a text file in the directory somewhere that has the API key and put the path to that in the same place in the local.env file to keep it clean.

# Project Structure
This explains where each file and directory needs to be located in your project for this CLI tester to work properly.

- `tests/` exists under the working directory
- `config/` exists under the working directory
- `local.env` exists under `config/`.
- `test_handler.py` exists under `tests/`
- `Tests.luau` exists under `tests/`

### Extra Notes:
The root directory is by default parented under Replicated Storage, test it as such.

# Rojo Compatibility
This tool mirrors Rojo file conventions without requiring rojo explicitly. It will copy the file structure under the root directory and create a .rbxlx file to upload the same way Rojo would. So if the tests pass, you know that the behaviors should work when you tell Rojo to copy the code into Studio. If you're not using Rojo, it will still work as long as you structure it like Rojo expects, it follows the same conventions. It's meant to supplement the Rojo pipeline, streamlining the testing process and encouraging developers to catch bugs early.

# Configuration Reference
| Name           | Description                                                                        | Required? |
| -------------- | ---------------------------------------------------------------------------------- | --------- |
| ROBLOX_API_KEY | The API key or a file path to a plain text file with the API key                   | Yes       |
| UNIVERSE_ID    | The universe Id of the dedicated test place                                        | Yes       |
| PLACE_ID       | The place Id of the dedicated test place                                           | Yes       |
| PROJECT_NAME   | The name of the root file in the built roblox instance. Defaults to the CWD's name | No        |
| ROOT_DIRECTORY | The name of the directory you want to build. Defaults to 'src' under the CWD.      | No        |

These required values are *not required if they are passed through CLI arguments* but they need to be passed through at least one medium.

## Where to Find: ROBLOX_API_KEY
After creating an API key at this website: [API Key Creation](https://create.roblox.com/dashboard/credentials), Roblox will give a giant string, that's the API key.

## Where to Find: UNIVERSE_ID
Go to your experiences here: [Experiences](https://create.roblox.com/dashboard/creations). Find the experience, click it to open it in the dashboard, and then the UniverseId should be in the URL. It should be the only long set of numbers but to be more precise here's where it can be found in relation to the other URL terms:
`https://create.roblox.com/dashboard/creations/experiences/!!!UNIVERSE ID!!!/overview`
Paste that into local.env.

## Where to Find: PLACE_ID
Go to your experiences here: [Experiences](https://create.roblox.com/dashboard/creations). Find the experience, and click the 3 dots when hovering over it. Then in the dropdown menu, find `Copy Start Place ID` and click that. Then paste it into `local.env`

# CLI Arguments

the .py file can take CLI arguments (using the `argparse` library) instead of the values passed in the .env file. *Using these arguments will overwrite values in the .env file*, but it is recommended to just fill out local.env since it's a lot easier to execute that way.

Any CLI arguments marked as required here are only required *if the values are not otherwise passed through `local.env`*

| Long Name        | Short Name | Description                                                                        | Required? |
| ---------------- | ---------- | ---------------------------------------------------------------------------------- | --------- |
| --help           | -h         | Shows CLI arguments and what they are                                              | No        |
| --api-key        | -k         | The API key or a file path to a plain text file with the API key                   | Yes       |
| --place          | -p         | The place Id of the dedicated test place                                           | Yes       |
| --universe       | -u         | The universe Id of the dedicated test place                                        | Yes       |
| --project-name   | -p         | The name of the root file in the built roblox instance. Defaults to the CWD's name | No        |
| --root-directory | -r         | The name of the directory you want to build. Defaults to 'src' under the CWD.      | No        |

# Contributing
The Python and luau separation is intentional. It is meant to allow developers who are only comfortable with luau to never have to touch the .py file. Try to keep that separation. I also put a considerable amount of effort into avoiding non standard Python libraries, so that the required setup ritual has the smallest barrier of entry possible. The .py file is not intended to be edited or viewed under normal use, but is meant to be transparent for people who want to know whats going on under the hood.

There is a stub function in the Python file meant for forking ease, a function by the name `parseLogs`, it's there if someone wants to handle the logs that are returned more explicitly than I currently handle them.

# Credits
Created by Chloricmass80
- @chloricmass80 on [Roblox](https://www.roblox.com/users/226463906/profile)
- @chloricmass on Discord (Chloric#8493)

# License
Licensed under the MIT License.