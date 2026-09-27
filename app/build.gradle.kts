import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

val configuredTranscriptionUrl = providers.gradleProperty("UNISCRIBE_TRANSCRIPTION_URL")
    .orElse("")
    .get()
    .replace("\\", "\\\\")
    .replace("\"", "\\\"")
android {
    namespace = "com.uniscribe.app"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.uniscribe.app"
        minSdk = 24
        targetSdk = 35
        versionCode = 1
        versionName = "1.0"

        buildConfigField(
            "String",
            "UNISCRIBE_TRANSCRIPTION_URL",
            "\"$configuredTranscriptionUrl\""
        )
    }

    buildFeatures {
        buildConfig = true
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

kotlin {
    compilerOptions {
        jvmTarget.set(JvmTarget.JVM_17)
    }
}

dependencies {
    testImplementation("junit:junit:4.13.2")
}
