from sklearn.model_selection import train_test_split
from sklearn.ensemble import IsolationForest
from sklearn.metrics import classification_report, confusion_matrix
import seaborn as sns
import matplotlib.pyplot as plt
import pandas as pd

#Loading preprocessed data
df = pd.read_csv("processed_hdfs.csv")
print(df.head())
print("Shape:", df.shape)

#Training-Testing spliting
x= df.drop(["BlockId","Label"],axis=1)
y=df["Label"]

x_train , x_test, y_train , y_test = train_test_split(
    x, y, test_size=0.2,
    stratify=y,
    random_state =42
)
print("Train shape : ", x_train.shape)
print("Test shape: ",x_test.shape)

#Isolation Forest
iso=IsolationForest(
    contamination = 0.03, #expected anomaly ratio is nearly 3%
    random_state=42
)
iso.fit(x_train)

#predict anomalies
y_pred = iso.predict(x_test)

#convert predictions
y_pred = [1 if x==-1 else 0 for x in y_pred]

#evaluation model
print(confusion_matrix(y_test, y_pred))
print(classification_report(y_test,y_pred))

#Confusion matrix plot
cm = confusion_matrix(y_test, y_pred)
sns.heatmap(cm, annot=True, fmt ="d",cmap="Blues")

plt.xlabel("Predicted")
plt.ylabel("Actual")
plt.title("Isolation Forest Confusion Matrix")

plt.show()


