package com.uniscribe.app

import android.app.Application
import com.uniscribe.app.di.AppContainer

class UniScribeApplication : Application() {
    lateinit var container: AppContainer
        private set

    override fun onCreate() {
        super.onCreate()
        container = AppContainer()
    }
}
