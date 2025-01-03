import azure.functions as func

app = func.FunctionApp()


@app.function_name(name="usage")
@app.timer_trigger(schedule="0 0 * * * *", arg_name="my_timer", run_on_startup=False)
def usage_func(my_timer: func.TimerRequest) -> None:
    usage.main(my_timer)


@app.function_name(name="monthly_usage")
@app.timer_trigger(
    schedule="0 10 */2 7,8 * *", arg_name="my_timer", run_on_startup=False
)
def monthly_usage_func(my_timer: func.TimerRequest) -> None:
    montly_usage.main(my_timer)
