from backend.evidence.read import read
import string

  

stop_words = set([
    "the", "is", "in", "and", "to", "of","into", "a", "an", "for", "on", "with", "as", "by", "at", "from", "that", "this", "it", "be", "or", "are","was", "were", "which", "but", "not", "can", "will", "would", "should", "could", "may", "might", "must", "shall", "do", "does", "did", "have", "has", "had","while", "if", "then", "else", "when", "where", "who", "whom", "whose", "what", "why", "how", "all", "any", "both", "each", "few", "more", "most", "other", "some", "such", "no", "nor", "only", "own", "same", "so","than","too","very","just","now","over","under","again","further","once"
])



def retrieve(question, records):

    question = question.lower()

    for char in string.punctuation:
        question = question.replace(char, "")

    words = question.split()     

    keywords = [word for word in words if word not in stop_words]

    results = []
    
    for record in records:
        matches = []
        content_text = " ".join(record["content"]).lower()

        for char in string.punctuation:
            content_text = content_text.replace(char, " ")
        
        content_words = set(content_text.split())

        matches = [word for word in keywords if word in content_words]
        
        

    

        score = len(matches) 

        if score > 0:   
            results.append({
                "record": record,
                "matches": matches,
                "score": score
                })   

    results.sort(key=lambda x: x["score"], reverse=True)

    return results
    
    

if __name__ == "__main__":
    records = read("samples/read.py")

    results = retrieve("How does the program split files into snippets?", records)

    for result in results:
        record = result["record"]

        print(
            f"{record['path']} "
            f"{record['start_line']}-{record['end_line']}"
        )

        print(f"Score: {result['score']}")
        print(f"Matched words: {result['matches']}")
        print()
